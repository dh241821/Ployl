from enum import IntEnum, Enum


class VehicleStatus(IntEnum):
    OFF_DUTY = 0
    STATION_AVAILABLE = 1
    EN_ROUTE_TO_CALL = 2
    ON_SCENE = 3
    EN_ROUTE_TO_DESTINATION = 4
    AT_DESTINATION = 5
    RADIO_AVAILABLE = 6
    SERVICE_TRIP = 7
    STANDBY_DELAYED = 8
    ALARMED_ACKNOWLEDGED = 9


class DifficultyLevel(Enum):
    BASIC = "basic"
    ADVANCED = "advanced"
    COMPLEX = "complex"


class IncidentStatus(Enum):
    CREATED = "created"
    DISPATCHED = "dispatched"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class VehicleType(Enum):
    RTW = "RTW"
    RTW_C = "RTW-C"
    NEF = "NEF"
    KTW = "KTW"
    KTW_B = "KTW-B"
    KI = "KI"
    NAH = "NAH"
    BKTW = "BKTW"
    BEL = "BEL"
    MTF = "MTF"
    OTHER = "OTHER"
