from django.conf import settings


def portal(request):
    return {"portal_name": settings.PORTAL_NAME}
