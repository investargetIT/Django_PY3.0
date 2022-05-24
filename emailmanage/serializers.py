from rest_framework import serializers

from emailmanage.models import emailgroupsendlist
from usersys.models import MyUser


class Usergroupsendlistserializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        fields = ('id', 'usernameC', 'email', 'mobile')


class Emailgroupsendlistserializer(serializers.ModelSerializer):
    class Meta:
        model = emailgroupsendlist
        exclude = ('is_deleted',)