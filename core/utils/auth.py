from django.shortcuts import redirect
from functools import wraps
#SOLO ES EJEMPLO
def auth_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('logged_in'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def maestro_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper
