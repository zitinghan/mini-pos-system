from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

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

class NewItem(StrictModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=99)
    option_ids: list[int] = Field(max_length=30)
    notes: str = Field(default='', max_length=240)

class PriceUpdate(StrictModel):
    price: int = Field(ge=0, le=1000000)

class Pay(StrictModel):
    method: Literal['CASH', 'QR', 'OTHER']
    received: int = Field(ge=0, le=10000000)
    expected_total: int = Field(ge=0)
    discard_drafts: bool = False

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
    beverage_host: str = Field(default='', max_length=253)
    beverage_port: int = Field(default=9100, ge=1, le=65535)

class OptionConfiguration(StrictModel):
    enabled: bool
    incompatible_with: list[int] = Field(default_factory=list, max_length=30)
