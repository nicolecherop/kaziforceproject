from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from ..models import Occupation, Skill


@login_required
def catalogue_search(request):
    query = request.GET.get('q', '').strip()[:100]
    model = Occupation if request.GET.get('kind') == 'occupation' else Skill
    if len(query) < 2:
        return JsonResponse({'results': []})
    items = model.objects.filter(
        Q(preferred_label__icontains=query)
        | Q(alternative_labels__icontains=query)
    )
    results = [
        {'id': item.pk, 'label': item.preferred_label}
        for item in items.only('pk', 'preferred_label')[:25]
    ]
    return JsonResponse({'results': results})
