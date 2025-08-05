import base64
from io import BytesIO

from app.serializers import UserSerializer
import pyotp
import qrcode
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class MyAccessTokenSerializer(TokenObtainPairSerializer):
    otp = serializers.CharField(required=False)

    def get_token(cls, user):
        token = super().get_token(user)

        token["role"] = user.role
        token["status"] = user.status

        return token

    def validate(self, attrs):

        data = super().validate(attrs)
        user = self.user

        if user.mfa_enabled:
            otp = attrs.get("otp")
            if not otp:
                raise serializers.ValidationError({"detail": "MFA_REQUIRED"})

            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(otp):
                raise serializers.ValidationError("Invalid OTP")

        data = super().validate(attrs)

        return {
            "access_token": data["access"],
        }


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyAccessTokenSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_me(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response({"user": serializer.data})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mfa_setup(request):
    user = request.user
    user.generate_totp_secret()

    totp = pyotp.TOTP(user.totp_secret)
    otp_uri = totp.provisioning_uri(name=user.email, issuer_name="Inventory App")

    qr = qrcode.make(otp_uri)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    return Response(
        {"otp_uri": otp_uri, "qr_code_base64": f"data:image/png;base64,{qr_b64}"}
    )
