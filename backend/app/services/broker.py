from __future__ import annotations

from app.config import settings


def transport_options() -> dict[str, object]:
    """Опції транспорту celery — однакові для клієнта (app/tasks.py) і
    воркера (workers/celery_app.py).

    Різні значення в цих двох місцях означали б, що producer і споживач
    намагаються говорити з брокером не зовсім однаково, а симптом цього —
    скан назавжди лишається `pending` без жодного запису в логах.

    `health_check_interval` — це не моніторинг, а єдина річ, без якої
    консьюмер може зависнути назавжди: BRPOP на напівмертвому з'єднанні
    не повертається і не падає. `socket_keepalive` змушує ядро слати
    keepalive, тож таке з'єднання рано чи пізно помічається.
    """
    return {
        "health_check_interval": settings.celery_broker_health_check_interval,
        "socket_keepalive": True,
    }