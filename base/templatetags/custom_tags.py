from django import template
register = template.Library()

@register.filter
def get_user_vote(obj, user):
    if not user.is_authenticated:
        return 0
    vote = obj.votes.filter(user=user).first()
    return vote.value if vote else 0
