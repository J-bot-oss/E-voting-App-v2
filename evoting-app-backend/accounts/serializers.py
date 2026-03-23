from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import VoterProfile
from elections.models import VotingStation

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "full_name", "role", "is_active", "is_verified", "date_joined",
            
        ]
        read_only_fields = ["id", "date_joined", "full_name",]

    def get_full_name(self, obj):
        return obj.get_full_name().strip()


class VoterProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    age = serializers.ReadOnlyField()
    station_name = serializers.CharField(source="station.name", read_only=True)

    class Meta:
        model = VoterProfile
        fields = [
            "id", "user", "national_id", "voter_card_number", "date_of_birth",
            "age", "gender", "address", "phone", "station", "station_name",
        ]
        read_only_fields = ["id", "age", "station_name"]


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class VoterLoginSerializer(serializers.Serializer):
    voter_card_number = serializers.CharField(max_length=12)
    password = serializers.CharField(write_only=True)

    def validate_voter_card_number(self, value):
        return value.strip().uppper()


class VoterRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
    national_id = serializers.CharField(max_length=50)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=VoterProfile.Gender.choices)
    address = serializers.CharField()
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    station_id = serializers.IntegerField()
    password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)
    
    def validate_full_name(self,value):
        return value.strip()
    

    def validate_national_id(self, value):
        cleaned_value = value.strip()
        if VoterProfile.objects.filter(national_id=cleaned_value).exists():
            raise serializers.ValidationError("A voter with this National ID already exists.")
        return cleaned_value
    
    def validate_email(self,value):
        return value.strip().lower()
    
    def validate_phone(self, value):
        return value.strip()
    
    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError(
                "You must be at least 18 years old."
            )
        return value

    def validate_station_id(self, value):
        if not VotingStation.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive voting station.")
        return value

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_passowrd": "Passwords do not match."})
        return data


class AdminCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[
        User.Role.SUPER_ADMIN,
        User.Role.ELECTION_OFFICER,
        User.Role.STATION_MANAGER,
        User.Role.AUDITOR,
        
    ])
    password = serializers.CharField(min_length=6, write_only=True)

    def validate_username(self, value):
        cleaned_value = value.strip()
        if User.objects.filter(username=cleaned_value).exists():
            raise serializers.ValidationError("Username already exists.")
        return cleaned_value
    
    def validate_full_name(self, value):
        return value.strip()
    
    def validate_email(self, value):
        cleaned_value = value.strip().lower()
        if User.objects.filter(email=cleaned_value).exists():
            raise serializers.ValidationError("Email already exists.")
        return cleaned_value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data


class VoterListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    voter_card_number = serializers.CharField(source="voter_profile.voter_card_number", read_only=True)
    station_id = serializers.IntegerField(source="voter_profile.station_id", read_only=True)
    age = serializers.ReadOnlyField(source="voter_profile.age")
    gender = serializers.CharField(source="voter_profile.gender", read_only=True)
    national_id = serializers.CharField(source="voter_profile.national_id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "full_name", "voter_card_number", "national_id",
            "station_id", "age", "gender", "is_verified", "is_active",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name().strip()


class AdminListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "role", "is_active", "date_joined"]

    def get_full_name(self, obj):
        return obj.get_full_name().strip()