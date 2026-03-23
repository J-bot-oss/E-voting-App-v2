from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count

from accounts.models import VoterProfile
from audit.services import AuditService
from elections.models import Candidate, Poll, PollPosition, VotingStation
from voting.models import Vote

User = get_user_model()


class VoteCastingService:
    def __init__(self):
        self._audit = AuditService()

    @transaction.atomic
    def cast(self, voter, validated_data):
        poll_id = validated_data["poll_id"]
        poll = Poll.objects.prefetch_related(
            "poll_positions__candidates",
            "stations",
        ).get(pk=poll_id)

        self._validate_poll_eligibility(voter, poll)

        poll_positions = {
            pp.id: pp
            for pp in PollPosition.objects.select_related("position", "poll").prefetch_related("candidates")
            .filter(poll=poll, pk__in=[item["poll_position_id"] for item in validated_data["votes"]])
        }

        created_votes = []

        for vote_item in validated_data["votes"]:
            poll_position_id = vote_item["poll_position_id"]
            pp = poll_positions.get(poll_position_id)

            if pp is None:
                raise ValueError(f"Poll position {poll_position_id} does not belong to this poll.")

            self._validate_position_vote(pp, poll, vote_item)

            if Vote.objects.filter(voter=voter, poll=poll, poll_position=pp).exists():
                raise ValueError(f"You have already voted for position {pp.position.title}.")

            vote = Vote(
                poll=poll,
                poll_position=pp,
                voter=voter,
                station=voter.voter_profile.station,
                abstained=vote_item.get("abstain", False),
            )

            if not vote.abstained:
                vote.candidate_id = vote_item["candidate_id"]

            vote.save()
            created_votes.append(vote)

        vote_hash = created_votes[0].vote_hash if created_votes else ""
        self._audit.log(
            "CAST_VOTE",
            voter.voter_profile.voter_card_number,
            f"Voted in poll: {poll.title} (Hash: {vote_hash})",
        )
        return created_votes

    def _validate_poll_eligibility(self, voter, poll):
        if poll.status != Poll.Status.OPEN:
            raise ValueError("This poll is not currently open for voting.")

        if not poll.stations.filter(pk=voter.voter_profile.station_id).exists():
            raise ValueError("Your station is not assigned to this poll.")

    def _validate_position_vote(self, poll_position, poll, vote_item):
        if poll_position.poll_id != poll.id:
            raise ValueError(f"Position {poll_position.id} does not belong to this poll.")

        abstain = vote_item.get("abstain", False)
        candidate_id = vote_item.get("candidate_id")

        if abstain and candidate_id is not None:
            raise ValueError("Cannot both abstain and select a candidate.")

        if not abstain and candidate_id is None:
            raise ValueError("You must either select a candidate or abstain.")

        if not abstain:
            if not poll_position.candidates.filter(pk=candidate_id).exists():
                raise ValueError(
                    f"Candidate {candidate_id} is not assigned to this position."
                )


class VoteHistoryService:
    def get_voter_history(self, voter):
        votes = (
            Vote.objects.filter(voter=voter)
            .select_related("poll", "poll_position__position", "candidate")
            .order_by("poll_id", "poll_position__position__title")
        )

        history_map = {}

        for vote in votes:
            poll_id = vote.poll_id
            if poll_id not in history_map:
                history_map[poll_id] = {
                    "poll_id": vote.poll.id,
                    "poll_title": vote.poll.title,
                    "poll_status": vote.poll.status,
                    "election_type": vote.poll.election_type,
                    "positions": [],
                }

            history_map[poll_id]["positions"].append(
                {
                    "position_title": vote.poll_position.position.title,
                    "candidate_name": vote.candidate.full_name if vote.candidate else None,
                    "abstained": vote.abstained,
                }
            )

        return list(history_map.values())


class ResultsService:
    def get_poll_results(self, poll_id):
        poll = Poll.objects.prefetch_related(
            "poll_positions__position",
            "poll_positions__candidates",
            "stations",
        ).get(pk=poll_id)

        total_eligible = User.objects.filter(
            role=User.Role.VOTER,
            is_verified=True,
            is_active=True,
            voter_profile__station__in=poll.stations.all(),
        ).count()

        total_voters_participated = (
            Vote.objects.filter(poll=poll)
            .values("voter_id")
            .distinct()
            .count()
        )

        turnout = (
            total_voters_participated / total_eligible * 100
            if total_eligible > 0 else 0
        )

        positions = [self._get_position_results(pp) for pp in poll.poll_positions.all()]

        return {
            "poll_id": poll.id,
            "poll_title": poll.title,
            "status": poll.status,
            "election_type": poll.election_type,
            "total_votes_cast": poll.total_votes_cast,
            "total_eligible": total_eligible,
            "turnout_percentage": round(turnout, 1),
            "positions": positions,
        }

    def _get_position_results(self, poll_position):
        votes = Vote.objects.filter(poll_position=poll_position)
        total = votes.count()
        abstain_count = votes.filter(abstained=True).count()

        candidate_votes = (
            votes.filter(abstained=False)
            .values("candidate_id", "candidate__full_name", "candidate__party")
            .annotate(count=Count("id"))
            .order_by("-count", "candidate__full_name")
        )

        results = []
        for rank, cv in enumerate(candidate_votes, 1):
            pct = (cv["count"] / total * 100) if total > 0 else 0
            results.append(
                {
                    "rank": rank,
                    "candidate_id": cv["candidate_id"],
                    "candidate_name": cv["candidate__full_name"],
                    "party": cv["candidate__party"],
                    "vote_count": cv["count"],
                    "percentage": round(pct, 1),
                    "is_winner": rank <= poll_position.position.max_winners,
                }
            )

        return {
            "position_id": poll_position.position.id,
            "position_title": poll_position.position.title,
            "max_winners": poll_position.position.max_winners,
            "results": results,
            "abstain_count": abstain_count,
            "total_votes": total,
        }

    def get_station_results(self, poll_id):
        poll = Poll.objects.prefetch_related(
            "stations",
            "poll_positions__position",
        ).get(pk=poll_id)

        station_data = []

        for station in poll.stations.all():
            registered = User.objects.filter(
                role=User.Role.VOTER,
                is_verified=True,
                is_active=True,
                voter_profile__station=station,
            ).count()

            station_votes = Vote.objects.filter(poll=poll, station=station)
            voters_voted = station_votes.values("voter").distinct().count()
            turnout = (voters_voted / registered * 100) if registered > 0 else 0

            positions = []
            for pp in poll.poll_positions.all():
                pos_votes = station_votes.filter(poll_position=pp)
                pos_total = pos_votes.count()
                abstain = pos_votes.filter(abstained=True).count()

                candidates = (
                    pos_votes.filter(abstained=False)
                    .values("candidate_id", "candidate__full_name", "candidate__party")
                    .annotate(count=Count("id"))
                    .order_by("-count", "candidate__full_name")
                )

                positions.append(
                    {
                        "position_title": pp.position.title,
                        "candidates": [
                            {
                                "name": c["candidate__full_name"],
                                "party": c["candidate__party"],
                                "votes": c["count"],
                                "percentage": round(c["count"] / pos_total * 100, 1)
                                if pos_total > 0 else 0,
                            }
                            for c in candidates
                        ],
                        "abstain_count": abstain,
                        "total": pos_total,
                    }
                )

            station_data.append(
                {
                    "station_id": station.id,
                    "station_name": station.name,
                    "station_location": station.location,
                    "registered_voters": registered,
                    "voters_voted": voters_voted,
                    "turnout_percentage": round(turnout, 1),
                    "positions": positions,
                }
            )

        return station_data


class StatisticsService:
    def get_system_overview(self):
        candidates = Candidate.objects.all()
        voters = User.objects.filter(role=User.Role.VOTER)
        stations = VotingStation.objects.all()
        polls = Poll.objects.all()

        return {
            "candidates": {
                "total": candidates.count(),
                "active": candidates.filter(is_active=True).count(),
            },
            "voters": {
                "total": voters.count(),
                "verified": voters.filter(is_verified=True).count(),
                "active": voters.filter(is_active=True).count(),
            },
            "stations": {
                "total": stations.count(),
                "active": stations.filter(is_active=True).count(),
            },
            "polls": {
                "total": polls.count(),
                "open": polls.filter(status=Poll.Status.OPEN).count(),
                "closed": polls.filter(status=Poll.Status.CLOSED).count(),
                "draft": polls.filter(status=Poll.Status.DRAFT).count(),
            },
            "total_votes": Vote.objects.count(),
        }

    def get_voter_demographics(self):
        profiles = VoterProfile.objects.select_related("user").filter(
            user__role=User.Role.VOTER
        )

        gender_counts = profiles.values("gender").annotate(count=Count("id")).order_by("gender")

        age_groups = defaultdict(int)
        for profile in profiles:
            age = profile.age
            if age <= 25:
                age_groups["18-25"] += 1
            elif age <= 35:
                age_groups["26-35"] += 1
            elif age <= 45:
                age_groups["36-45"] += 1
            elif age <= 55:
                age_groups["46-55"] += 1
            elif age <= 65:
                age_groups["56-65"] += 1
            else:
                age_groups["65+"] += 1

        return {
            "gender": list(gender_counts),
            "age_groups": dict(age_groups),
        }

    def get_station_load(self):
        stations = VotingStation.objects.filter(is_active=True)
        data = []

        for station in stations:
            data.append(
                {
                    "station_id": station.id,
                    "station_name": station.name,
                    "registered": station.registered_voter_count,
                    "capacity": station.capacity,
                    "load_percentage": station.load_percentage,
                }
            )

        return data

    def get_party_distribution(self):
        return list(
            Candidate.objects.filter(is_active=True)
            .values("party")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    def get_education_distribution(self):
        return list(
            Candidate.objects.filter(is_active=True)
            .values("education")
            .annotate(count=Count("id"))
            .order_by("education")
        )