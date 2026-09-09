from allauth.account.models import EmailAddress

FEATURES = frozenset({"analysis", "lookup_text", "vehicle_options", "locations", "vehicle_defaults"})

def feature_access(user):
    allowed = bool(user and user.is_authenticated and user.is_active and EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists())
    return {name: allowed for name in sorted(FEATURES)}

def has_feature(user, name):
    return feature_access(user).get(name, False)
