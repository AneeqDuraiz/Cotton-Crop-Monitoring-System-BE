from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from users.serializers import UserSerializer
from users.models import User
import jwt, datetime


# Create your views here.
class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    

class LoginView(APIView):
    def post(self, request):
        email= request.data['email']
        password = request.data['password']

        user = User.objects.filter(email=email).first()

        if user is None: 
            return Response({"error": "Invalid email address"}, status= 400)
        
        if not user.check_password(password):
            return Response({"error": "Invalid password"}, status= 400)
        
        payload = {
            'id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2),
            'iat': datetime.datetime.utcnow()
        }

        token = jwt.encode(payload, 'secret', algorithm='HS256')

        response = Response()

        response.set_cookie(key='jwt', value=token, httponly=True)
        response.data = {
            'jwt': token
        }
        return response


class UserView(APIView):

    def get(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({"Authentication Failed": "No JWT tokken found"}, status= 400)

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({"Authentication Failed": "Expired JWT Signature Error"}, status= 400)

        user = User.objects.filter(id=payload['id']).first()
        serializer = UserSerializer(user)
        return Response(serializer.data)
         

class LogoutView(APIView):
    def post(self, request):
        response = Response()
        response.delete_cookie('jwt')
        response.data = {
            'message': 'Logout success'
        }
        return response
