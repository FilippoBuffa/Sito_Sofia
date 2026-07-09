from app.extensions import db

GROUP_LETTERS = list("ABCDEFGHIJ")

LOCATION_CHOICES = [
    ("VAS", "VAS"),
    ("VGR", "VGR"),
    ("VSU", "VSU"),
    ("VOL", "VOL"),
    ("VKE", "VKE"),
    ("VYS", "VYS"),
    ("VMI", "VMI"),
    ("external", "External Customer"),
]

MANUFACTURING_PROCESS_CHOICES = [
    ("normal_production", "Vernay Documented Normal Production Part"),
    ("experimental", "Vernay Documented Experimental Part"),
    ("outside_vendor", "Outside Vendor Documented Part"),
    ("customer_competitor", "Customer/Competitor Part"),
    ("other", "Other"),
]

GROUP_TYPE_CHOICES = [
    ("control", "Control"),
    ("experimental", "Experimental"),
    ("n_a", "N/A"),
]

VALVE_TYPES = [
    "assembly", "armature", "ball check assembly", "ball/spring assy",
    "battery vent valve assembly", "battery vent valve assembly seat",
    "bi-di", "bi di", "bi-di vent valve assembly", "bongo", "breather assy",
    "combo", "combo duckbill", "combination", "competitor disc valve",
    "cross slit bi-di", "cross slit duckbill", "diaphragm", "disc", "disc valve",
    "dispensing valve", "dock gasket", "dome", "dome valve", "drain valve assembly",
    "duckbill", "duckbill assembly", "duckbill assy", "duckbill seal", "duckdisk",
    "eurovalve", "fimo assembly", "fimo body (no cap)", "fito assembly",
    "flow control", "flow washer", "hot water flow control", "inserted diaphragm",
    "introducer valve", "inverted dome valve", "inverted spherical dome", "iv valve",
    "level switch diaphragm", "magnetically adjustable hydrocephalus shunt valve",
    "medical assembly", "membrane", "mini duckbill", "mini tito assy", "mini umbrella",
    "mixing valve diaphragm", "mimo assembly", "nis site", "poppet",
    "rear tube feed valve", "reed valve assembly", "reverse umbrella",
    "semi permeable membrane", "semi-permeable membrane", "septum", "slit diaphragm",
    "spring loaded poppet", "stainless steel check valve", "supravalve",
    "supravalve assy", "t-valve assy", "tank vent assy", "thermal barrier",
    "timo assembly", "tito assembly", "trans vent valve assembly", "tube valve",
    "umbrella", "umbrella assembly", "umbrella/cap assembly", "umbrella/dome combo",
    "vent valve assembly", "v-ball", "v-seat", "v-seat w/ spring loaded ball",
]


class PartGroup(db.Model):
    __tablename__ = "part_group"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("test_request.id"), nullable=False)
    group_letter = db.Column(db.String(1), nullable=False)

    # --- Inherited from test info (editable per group) ---
    location = db.Column(db.String(32), nullable=True)
    valve_type = db.Column(db.String(128), nullable=True)
    valve_type_other = db.Column(db.String(256), nullable=True)
    part_number = db.Column(db.String(64), nullable=True)

    # --- Part INFO fields ---
    group_id = db.Column(db.String(64), nullable=True)
    quantity = db.Column(db.Integer, nullable=True)
    group_type = db.Column(db.String(20), nullable=True)
    manufacturing_process = db.Column(db.String(30), nullable=True)
    manufacturing_process_other = db.Column(db.String(256), nullable=True)
    inspected = db.Column(db.Boolean, nullable=True)

    # Test Group Summary Information
    part_type = db.Column(db.String(128), nullable=True)
    vl_part_number = db.Column(db.String(64), nullable=True)
    va_number = db.Column(db.String(64), nullable=True)
    x_number = db.Column(db.String(64), nullable=True)
    material_lab_code = db.Column(db.String(64), nullable=True)
    material_prod_code = db.Column(db.String(64), nullable=True)
    batch_no = db.Column(db.String(64), nullable=True)
    alternate_batch_no = db.Column(db.String(64), nullable=True)
    production_location = db.Column(db.String(128), nullable=True)
    mold_date = db.Column(db.Date, nullable=True)
    post_cure = db.Column(db.String(128), nullable=True)
    mold_tool_number = db.Column(db.String(64), nullable=True)
    other_description = db.Column(db.Text, nullable=True)

    @property
    def manufacturing_process_label(self):
        return dict(MANUFACTURING_PROCESS_CHOICES).get(self.manufacturing_process, self.manufacturing_process or "")

    @property
    def group_type_label(self):
        return dict(GROUP_TYPE_CHOICES).get(self.group_type, self.group_type or "")

    @property
    def location_label(self):
        return dict(LOCATION_CHOICES).get(self.location, self.location or "")

    @property
    def valve_type_display(self):
        if self.valve_type == "other":
            return self.valve_type_other or "Other"
        return self.valve_type or ""

    def __repr__(self):
        return f"<PartGroup {self.group_letter} req={self.request_id}>"
