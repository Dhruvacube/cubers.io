""" Routes related to a user's profile. """

from flask import render_template
from flask_login import current_user

from app import CUBERS_APP
from app.business.user_history import get_user_competition_history
from app.persistence.comp_manager import get_user_participated_competitions_count
from app.persistence.user_manager import get_user_by_username
from app.persistence.user_results_manager import get_user_completed_solves_count
from app.persistence.events_manager import get_events_id_name_mapping, get_all_WCA_events,\
    get_all_non_WCA_events
from app.persistence.user_site_rankings_manager import get_site_rankings_for_user
from app.routes.util import is_admin_viewing

# -------------------------------------------------------------------------------------------------

@CUBERS_APP.route('/u/<username>/')
def profile(username):
    """ A route for showing a user's profile. """

    user = get_user_by_username(username)
    if not user:
        return ("oops, can't find a user with username '{}'".format(username), 404)

    # Determine whether an admin is viewing the page
    show_admin = is_admin_viewing()

    # Determine whether we're showing blacklisted results
    include_blacklisted = should_show_blacklisted_results(username, show_admin)

    # Get the user's competition history
    history = get_user_competition_history(user, include_blacklisted=include_blacklisted)

    gold_count = 0
    silver_count = 0
    bronze_count = 0
    for _, comp_event_results_dict in history.items():
        for _, results in comp_event_results_dict.items():
            gold_count   += 1 if results.was_gold_medal   else 0
            silver_count += 1 if results.was_silver_medal else 0
            bronze_count += 1 if results.was_bronze_medal else 0

    import sys
    print(gold_count, file=sys.stderr)
    print(silver_count, file=sys.stderr)
    print(bronze_count, file=sys.stderr)

    # Get some other interesting stats
    solve_count = get_user_completed_solves_count(user.id)
    comps_count = get_user_participated_competitions_count(user.id)

    # Get a dictionary of event ID to names, to facilitate rendering some stuff in the template
    event_id_name_map = get_events_id_name_mapping()

    # See if the user has any recorded site rankings. If they do, extract the data as a dict so we
    # can build their site ranking table
    site_rankings_record = get_site_rankings_for_user(user.id)
    if site_rankings_record:
        site_rankings = site_rankings_record.get_site_rankings_and_pbs()

        # Get sum of ranks
        sor_all     = site_rankings_record.get_combined_sum_of_ranks()
        sor_wca     = site_rankings_record.get_WCA_sum_of_ranks()
        sor_non_wca = site_rankings_record.get_non_WCA_sum_of_ranks()

        # If it exists, get the timestamp formatted like "2019 Jan 11"
        if site_rankings_record.timestamp:
            rankings_ts = site_rankings_record.timestamp.strftime('%Y %b %d')

        # If there is no timestamp, just say that the rankings as accurate as of the last comp
        # This should only happen briefly after I add the timestamp to the rankings table,
        # but before the rankings are re-calculated
        else:
            rankings_ts = "last competition-ish"

    else:
        rankings_ts   = None
        site_rankings = None
        sor_all       = None
        sor_wca       = None
        sor_non_wca   = None

    return render_template("user/profile.html", user=user, solve_count=solve_count,\
        comp_count=comps_count, history=history, rankings=site_rankings,\
        event_id_name_map=event_id_name_map, rankings_ts=rankings_ts,\
        is_admin_viewing=show_admin, sor_all=sor_all, sor_wca=sor_wca, sor_non_wca=sor_non_wca)

# -------------------------------------------------------------------------------------------------

def should_show_blacklisted_results(profile_username, is_admin_here):
    """ Determine if we want to show blacklisted results in the competition history. """

    # If the user viewing a page is an admin, they can see blacklisted results
    if is_admin_here:
        return True

    # Non-logged-in users can't see blacklisted results
    if not current_user.is_authenticated:
        return False

    # Users can see their own blacklisted results
    if current_user.username == profile_username:
        return True

    # Everybody else can't see blacklisted results
    return False
