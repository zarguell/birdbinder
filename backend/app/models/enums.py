import enum


class PoseVariant(str, enum.Enum):
    perching = "perching"
    flying = "flying"
    swimming = "swimming"
    foraging = "foraging"
    singing = "singing"
    nesting = "nesting"
    courtship = "courtship"
    other = "other"


class SightingStatus(str, enum.Enum):
    pending = "pending"
    identified = "identified"
    failed = "failed"
    cancelled = "cancelled"


class JobType(str, enum.Enum):
    identify = "identify"
    generate_card = "generate_card"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TradeStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    cancelled = "cancelled"
