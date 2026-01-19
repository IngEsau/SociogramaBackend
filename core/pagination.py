from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Paginación estándar para la mayoría de endpoints
    - 20 items por página por defecto
    - El cliente puede pedir hasta 100 items
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    # Nombres de parámetros en español (opcional)
    # page_query_param = 'pagina'


class LargeResultsSetPagination(PageNumberPagination):
    """
    Paginación para datasets grandes
    - 50 items por página por defecto
    - El cliente puede pedir hasta 200 items
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class SmallResultsSetPagination(PageNumberPagination):
    """
    Paginación para listas pequeñas o previews
    - 10 items por página por defecto
    - El cliente puede pedir hasta 50 items
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50