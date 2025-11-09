from app.schemas.vehicles import (
    CrewMemberCreate,
    CrewMemberRead,
    CrewMemberUpdate,
    VehicleCreate,
    VehicleRead,
    VehicleStatusChange,
    VehicleUpdate,
)
from app.schemas.incidents import IncidentCreate, IncidentRead, IncidentUpdate
from app.schemas.hospitals import HospitalCreate, HospitalRead, HospitalUpdate
from app.schemas.personnel import PersonnelCreate, PersonnelRead, PersonnelUpdate
from app.schemas.patients import (
    PatientCreate,
    PatientRead,
    PatientTransportCreate,
    PatientTransportRead,
    PatientTransportUpdate,
    PatientUpdate,
)

__all__ = [
    "CrewMemberCreate",
    "CrewMemberRead",
    "CrewMemberUpdate",
    "VehicleCreate",
    "VehicleRead",
    "VehicleStatusChange",
    "VehicleUpdate",
    "IncidentCreate",
    "IncidentRead",
    "IncidentUpdate",
    "HospitalCreate",
    "HospitalRead",
    "HospitalUpdate",
    "PersonnelCreate",
    "PersonnelRead",
    "PersonnelUpdate",
    "PatientCreate",
    "PatientRead",
    "PatientTransportCreate",
    "PatientTransportRead",
    "PatientTransportUpdate",
    "PatientUpdate",
]
