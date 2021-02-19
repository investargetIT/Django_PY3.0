from rest_framework import serializers

from activity.models import activity
from third.views.qiniufile import getUrlWithBucketAndKey


class ActivitySerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    class Meta:
        model = activity
        exclude = ('deleteduser', 'deletedtime', 'createuser', 'createdtime', 'lastmodifyuser', 'lastmodifytime','is_deleted')

    def get_url(self,obj):
        if obj.key and obj.bucket:
            return getUrlWithBucketAndKey(obj.bucket, obj.key)
        return None