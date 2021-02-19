"""invest URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from rest_framework_swagger.views import get_swagger_view

import APIlog.urls
import mongoDoc.urls
import org.urls
import proj.urls
import usersys.urls
import timeline.urls
import third.urls
import dataroom.urls
import sourcetype.urls
import msg.urls
import emailmanage.urls
import activity.urls
import BD.urls
schema_view = get_swagger_view(title='investarget-api-3.0')

urlpatterns = [
    url(r'^$', schema_view)
]
urlpatterns += [
    url(r'^admin/', admin.site.urls),
    url(r'^user/', include(usersys.urls)),
    url(r'^proj/',include(proj.urls)),
    url(r'^org/',include(org.urls)),
    url(r'^timeline/',include(timeline.urls)),
    url(r'^dataroom/',include(dataroom.urls)),
    url(r'^service/',include(third.urls)),
    url(r'^source/', include(sourcetype.urls)),
    url(r'^log/', include(APIlog.urls)),
    url(r'^msg/', include(msg.urls)),
    url(r'^mongolog/', include(mongoDoc.urls)),
    url(r'^emailmanage/', include(emailmanage.urls)),
    url(r'^activity/', include(activity.urls)),
    url(r'^bd/', include(BD.urls)),
]
