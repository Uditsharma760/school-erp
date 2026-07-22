from .models import AcademicSession, SchoolProfile

def school_context(request):
    return {
        "school_profile": SchoolProfile.objects.first(),
        "active_session": AcademicSession.objects.filter(is_active=True).first(),
    }
