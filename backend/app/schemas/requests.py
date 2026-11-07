from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Credentials(StrictModel):
    name: str = Field(min_length=1, max_length=80, pattern=r'^\S(?:.*\S)?$')
    pin: str = Field(pattern=r'^[0-9]{6,12}$')

class Setup(Credentials):
    setup_token: str

class NewUser(Credentials):
    role: Literal['STAFF', 'ADMIN'] = 'STAFF'

class NewBatch(StrictModel):
    session_id: int = Field(gt=0)
    notes: str = Field(default='', max_length=500)

class SubmitBatch(StrictModel):
    notes: str | None = Field(default=None, max_length=500)
    prepaid_label: bool | None = None

class CancelItem(StrictModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(default='顾客取消', min_length=1, max_length=240)

class CancelTable(StrictModel):
    expected_change_token: str = Field(min_length=64, max_length=64)
    reason: str = Field(default='顾客取消', min_length=1, max_length=240)

class TableNotes(StrictModel):
    expected_revision: int = Field(ge=1)
    notes: str = Field(max_length=500)

class BatchDetails(TableNotes):
    prepaid_label: bool

class NewItem(StrictModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=99)
    option_ids: list[int] = Field(max_length=30)
    notes: str = Field(default='', max_length=240)

class EditItem(NewItem):
    expected_revision: int = Field(ge=1)
    expected_unit_price: int = Field(ge=0)

class PriceUpdate(StrictModel):
    price: int = Field(ge=0, le=1000000)

class CustomItem(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    unit_price: int = Field(ge=0, le=1000000)
    quantity: int = Field(ge=1, le=99)
    category_code: Literal['MAINS', 'SNACKS', 'DRINKS', 'BEER']
    printer_group: Literal['KITCHEN', 'RICE', 'BEVERAGE']
    takeaway: bool = False
    notes: str = Field(default='', max_length=240)
    bottles_per_unit: int = Field(default=0, ge=0, le=99)

    @model_validator(mode='after')
    def valid_custom_item(self):
        self.name, self.notes = self.name.strip(), self.notes.strip()
        if not self.name or any(ord(char) < 32 or ord(char) == 127 for char in self.name):
            raise ValueError('请输入有效的自定义餐点名称')
        if (self.category_code == 'BEER') != (self.bottles_per_unit > 0):
            raise ValueError('啤酒请填写每份瓶数；其他分类的瓶数须为零')
        return self

class EditCustomItem(CustomItem):
    expected_revision: int = Field(ge=1)

class Pay(StrictModel):
    method: Literal['CASH', 'QR', 'OTHER']
    received: int = Field(ge=0, le=10000000)
    expected_total: int = Field(ge=0)
    final_total: int | None = Field(default=None, ge=0, le=10000000)
    offer_reason: str = Field(default='', max_length=240)
    discard_drafts: bool = False
    print_receipt: bool = False

class PrinterSettings(StrictModel):
    mode: Literal['mock', 'network'] = 'mock'
    simulation: Literal['success', 'connection_failure', 'timeout', 'uncertain'] = 'success'
    host: str = Field(default='', max_length=253)
    port: int = Field(default=9100, ge=1, le=65535)
    print_mode: Literal['raster', 'text'] = 'raster'
    encoding: str = Field(default='gb18030', max_length=40)
    profile: str = Field(default='default', max_length=80)
    raster_command: Literal['bitImageRaster', 'graphics', 'bitImageColumn'] = 'bitImageRaster'
    width: int = Field(default=384, ge=192, le=576)
    feed: int = Field(default=3, ge=0, le=10)
    cutter: bool = False
    separate_stations: bool = False
    kitchen_host: str = Field(default='', max_length=253)
    kitchen_port: int = Field(default=9100, ge=1, le=65535)
    rice_host: str = Field(default='', max_length=253)
    rice_port: int = Field(default=9100, ge=1, le=65535)
    beverage_host: str = Field(default='', max_length=253)
    beverage_port: int = Field(default=9100, ge=1, le=65535)
    receipt_mode: Literal['mock', 'network', 'windows'] = 'mock'
    receipt_host: str = Field(default='', max_length=253)
    receipt_port: int = Field(default=9100, ge=1, le=65535)
    receipt_printer_name: str = Field(default='', max_length=200)
    receipt_width: int = Field(default=384, ge=192, le=576)
    receipt_paper_mm: Literal[55, 58, 80] = 58
    receipt_cutter: bool = False
    receipt_simulation: Literal['success', 'connection_failure', 'timeout', 'uncertain'] = 'success'

class OptionConfiguration(StrictModel):
    enabled: bool
    incompatible_with: list[int] = Field(default_factory=list, max_length=30)


class AvailabilityUpdate(StrictModel):
    sold_out: bool


class PromotionUpdate(StrictModel):
    starts_on: str
    ends_on: str
    unit_price: int = Field(gt=0, le=1000000)
    enabled: bool = True

    @model_validator(mode='after')
    def valid_dates(self):
        from datetime import date
        start, end = date.fromisoformat(self.starts_on), date.fromisoformat(self.ends_on)
        if start > end:
            raise ValueError('Promotion end date must be on or after the start date')
        self.starts_on, self.ends_on = start.isoformat(), end.isoformat()
        return self
