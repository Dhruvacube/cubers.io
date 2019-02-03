#pylint: disable=C0111
from .auth import login, logout, authorize
from .home import index
from .admin import gc_select, gc_select_user
from .util import current_comp, prev_results, is_admin_viewing
from .results import results_list
from .user import profile, edit_settings
from .events import event_results, sum_of_ranks