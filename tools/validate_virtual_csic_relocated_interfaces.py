"""Run unchanged level/error API checks against relocated controller."""
import validate_virtual_csic_interfaces as regression
from virtual_csic_relocated_patch import patch

if __name__=='__main__':
    regression.patch=patch
    regression.main('virtual-csic-relocated')
