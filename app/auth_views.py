from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class MyAccessTokenSerializer(TokenObtainPairSerializer):
    def get_token(cls, user):
        token = super().get_token(user)

        token["role"] = user.role
        token["status"] = user.status

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        return {
            "access_token": data["access"],
        }


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyAccessTokenSerializer
