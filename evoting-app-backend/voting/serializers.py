from rest_framework import serializers


class CastVoteItemSerializer(serializers.Serializer):
    poll_position_id = serializers.IntegerField()
    candidate_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    abstain = serializers.BooleanField(default=False)

    def validate(self, data):
        candidate_id = data.get("candidate_id")
        abstain = data.get("abstain", False)

        if abstain and candidate_id is not None:
            raise serializers.ValidationError(
                "Cannot both abstain and select a candidate."
            )

        if not abstain and candidate_id is None:
            raise serializers.ValidationError(
                "You must either select a candidate or abstain."
            )

        return data


class CastVoteSerializer(serializers.Serializer):
    poll_id = serializers.IntegerField()
    votes = CastVoteItemSerializer(many=True)

    def validate_votes(self, value):
        if not value:
            raise serializers.ValidationError("At least one vote item is required.")

        poll_position_ids = [item["poll_position_id"] for item in value]
        if len(poll_position_ids) != len(set(poll_position_ids)):
            raise serializers.ValidationError(
                "Duplicate poll position IDs are not allowed."
            )

        return value


class VoteHistorySerializer(serializers.Serializer):
    poll_id = serializers.IntegerField()
    poll_title = serializers.CharField()
    poll_status = serializers.CharField()
    election_type = serializers.CharField()
    positions = serializers.ListField()


class PositionResultSerializer(serializers.Serializer):
    position_id = serializers.IntegerField()
    position_title = serializers.CharField()
    max_winners = serializers.IntegerField()
    results = serializers.ListField()
    abstain_count = serializers.IntegerField()
    total_votes = serializers.IntegerField()


class PollResultSerializer(serializers.Serializer):
    poll_id = serializers.IntegerField()
    poll_title = serializers.CharField()
    status = serializers.CharField()
    election_type = serializers.CharField()
    total_votes_cast = serializers.IntegerField()
    total_eligible = serializers.IntegerField()
    turnout_percentage = serializers.FloatField()
    positions = PositionResultSerializer(many=True)


class StationResultSerializer(serializers.Serializer):
    station_id = serializers.IntegerField()
    station_name = serializers.CharField()
    station_location = serializers.CharField()
    registered_voters = serializers.IntegerField()
    voters_voted = serializers.IntegerField()
    turnout_percentage = serializers.FloatField()
    positions = serializers.ListField()