from django.db import transaction

from audit.services import AuditService
from elections.models import Candidate, Poll, PollPosition, Position, VotingStation


class CandidateService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        candidate = Candidate.objects.create(created_by=created_by, **validated_data)
        self._audit.log(
            "CREATE_CANDIDATE",
            created_by.username,
            f"Created candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def update(self, candidate, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(candidate, key, value)
        candidate.save()

        self._audit.log(
            "UPDATE_CANDIDATE",
            updated_by.username,
            f"Updated candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def deactivate(self, candidate_id, deactivated_by):
        candidate = Candidate.objects.get(pk=candidate_id)
        candidate.is_active = False
        candidate.save(update_fields=["is_active"])

        self._audit.log(
            "DEACTIVATE_CANDIDATE",
            deactivated_by.username,
            f"Deactivated candidate: {candidate.full_name} (ID: {candidate.id})",
        )
        return candidate

    def search(self, query_params):
        qs = Candidate.objects.all()

        if name := query_params.get("name"):
            qs = qs.filter(full_name__icontains=name.strip())

        if party := query_params.get("party"):
            qs = qs.filter(party__icontains=party.strip())

        if education := query_params.get("education"):
            qs = qs.filter(education=education)

        candidates = list(qs)

        if min_age := query_params.get("min_age"):
            candidates = [c for c in candidates if c.age >= int(min_age)]

        if max_age := query_params.get("max_age"):
            candidates = [c for c in candidates if c.age <= int(max_age)]

        return candidates


class VotingStationService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        station = VotingStation.objects.create(created_by=created_by, **validated_data)
        self._audit.log(
            "CREATE_STATION",
            created_by.username,
            f"Created station: {station.name} (ID: {station.id})",
        )
        return station

    def update(self, station, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(station, key, value)
        station.save()

        self._audit.log(
            "UPDATE_STATION",
            updated_by.username,
            f"Updated station: {station.name} (ID: {station.id})",
        )
        return station

    def deactivate(self, station_id, deactivated_by):
        station = VotingStation.objects.get(pk=station_id)
        station.is_active = False
        station.save(update_fields=["is_active"])

        self._audit.log(
            "DEACTIVATE_STATION",
            deactivated_by.username,
            f"Deactivated station: {station.name} (ID: {station.id})",
        )
        return station


class PositionService:
    def __init__(self):
        self._audit = AuditService()

    def create(self, validated_data, created_by):
        position = Position.objects.create(created_by=created_by, **validated_data)
        self._audit.log(
            "CREATE_POSITION",
            created_by.username,
            f"Created position: {position.title} (ID: {position.id})",
        )
        return position

    def update(self, position, validated_data, updated_by):
        for key, value in validated_data.items():
            setattr(position, key, value)
        position.save()

        self._audit.log(
            "UPDATE_POSITION",
            updated_by.username,
            f"Updated position: {position.title} (ID: {position.id})",
        )
        return position

    def deactivate(self, position_id, deactivated_by):
        position = Position.objects.get(pk=position_id)
        position.is_active = False
        position.save(update_fields=["is_active"])

        self._audit.log(
            "DEACTIVATE_POSITION",
            deactivated_by.username,
            f"Deactivated position: {position.title} (ID: {position.id})",
        )
        return position


class PollService:
    def __init__(self):
        self._audit = AuditService()

    @transaction.atomic
    def create(self, validated_data, created_by):
        poll = Poll.objects.create(
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            election_type=validated_data["election_type"],
            start_date=validated_data["start_date"],
            end_date=validated_data["end_date"],
            status=Poll.Status.DRAFT,
            created_by=created_by,
        )

        poll.stations.set(
            VotingStation.objects.filter(pk__in=validated_data["station_ids"])
        )

        for pos_id in validated_data["position_ids"]:
            PollPosition.objects.create(
                poll=poll,
                position_id=pos_id,
            )

        self._audit.log(
            "CREATE_POLL",
            created_by.username,
            f"Created poll: {poll.title} (ID: {poll.id})",
        )
        return poll

    def update(self, poll, validated_data, updated_by):
        if poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot update an open poll. Close it first.")

        for key, value in validated_data.items():
            setattr(poll, key, value)
        poll.save()

        self._audit.log(
            "UPDATE_POLL",
            updated_by.username,
            f"Updated poll: {poll.title} (ID: {poll.id})",
        )
        return poll

    @transaction.atomic
    def delete(self, poll_id, deleted_by):
        poll = Poll.objects.get(pk=poll_id)

        if poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot delete an open poll. Close it first.")

        title = poll.title
        poll.delete()

        self._audit.log(
            "DELETE_POLL",
            deleted_by.username,
            f"Deleted poll: {title}",
        )

    def toggle_status(self, poll_id, action, toggled_by):
        poll = Poll.objects.prefetch_related("poll_positions__candidates").get(pk=poll_id)
        previous_status = poll.status

        if action == "open":
            if previous_status not in (Poll.Status.DRAFT, Poll.Status.CLOSED):
                raise ValueError(f"Cannot open a poll with status: {previous_status}")

            if previous_status == Poll.Status.DRAFT:
                all_positions_have_candidates = all(
                    pp.candidates.exists() for pp in poll.poll_positions.all()
                )
                if not all_positions_have_candidates:
                    raise ValueError("Cannot open poll until all positions have candidates assigned.")

            poll.status = Poll.Status.OPEN
            log_action = "OPEN_POLL" if previous_status == Poll.Status.DRAFT else "REOPEN_POLL"

        elif action == "close":
            if previous_status != Poll.Status.OPEN:
                raise ValueError("Only open polls can be closed.")

            poll.status = Poll.Status.CLOSED
            log_action = "CLOSE_POLL"

        else:
            raise ValueError(f"Invalid action: {action}")

        poll.save(update_fields=["status"])

        self._audit.log(
            log_action,
            toggled_by.username,
            f"{log_action.replace('_', ' ').title()}: {poll.title}",
        )
        return poll

    def assign_candidates(self, poll_position_id, candidate_ids, assigned_by):
        poll_position = PollPosition.objects.select_related("poll", "position").get(
            pk=poll_position_id
        )

        if poll_position.poll.status == Poll.Status.OPEN:
            raise ValueError("Cannot modify candidates of an open poll.")

        eligible = Candidate.objects.filter(
            pk__in=candidate_ids,
            is_active=True,
            is_approved=True,
        )

        if eligible.count() != len(set(candidate_ids)):
            raise ValueError("Some candidates are invalid, inactive, or not approved.")

        poll_position.candidates.set(eligible)

        self._audit.log(
            "ASSIGN_CANDIDATES",
            assigned_by.username,
            f"Assigned {eligible.count()} candidates to {poll_position.position.title} "
            f"in poll: {poll_position.poll.title}",
        )
        return poll_position