""" Methods for processing UserEventResults. """

from app.persistence.comp_manager import get_comp_event_by_id
from app.persistence.user_results_manager import get_pb_single_event_results_except_current_comp,\
    get_pb_average_event_results_except_current_comp
from app.persistence.models import UserEventResults, UserSolve, EventFormat
from app.util.events_util import determine_bests, determine_best_single, determine_event_result
from app.util.reddit_util import build_times_string

# -------------------------------------------------------------------------------------------------

# The front-end dictionary keys
COMMENT     = 'comment'
SOLVES      = 'scrambles' # Because the solve times are paired with the scrambles in the front end
TIME        = 'time'
SCRAMBLE_ID = 'id'
IS_DNF      = 'isDNF'
IS_PLUS_TWO = 'isPlusTwo'

# Other useful constant values
FMC          = 'FMC'
BLIND_EVENTS = ('2BLD', '3BLD', '4BLD', '5BLD')

# -------------------------------------------------------------------------------------------------

def build_user_event_results(user_events_dict, user):
    """ Builds a UserEventsResult object from a dictionary coming in from the front-end, which
    contains the competition event ID and the user's solves paired with the scrambles. """

    # This dictionary just has one key/value pair, get the relevant info out of it
    comp_event_id   = list(user_events_dict.keys())[0]
    comp_event_dict = user_events_dict[comp_event_id]
    comment = comp_event_dict.get(COMMENT, '')

    # Retrieve the CompetitionEvent from the DB and get the event name, format, and expected solves
    comp_event          = get_comp_event_by_id(comp_event_id)
    event_id            = comp_event.Event.id
    event_name          = comp_event.Event.name
    event_format        = comp_event.Event.eventFormat
    expected_num_solves = comp_event.Event.totalSolves

    # Create the actual UserEventResults
    results = UserEventResults(comp_event_id=comp_event_id, comment=comment)

    # Build up a list of UserSolves, and set those in the as the solves for this UserEventREsults
    solves = build_user_solves(comp_event_dict[SOLVES])
    results.set_solves(solves)

    # Set the best single and overall average for this event
    set_single_and_average(results, expected_num_solves, event_format)

    # Determine if the user has completed their results for this event
    set_is_complete(results, event_format, expected_num_solves)

    if results.is_complete:
        # Set the result (either best single, mean, or average) depending on event format
        results.result = determine_event_result(results.single, results.average, event_format)

        # Store the "times string" so we don't have to recalculate this again later.
        # It's fairly expensive, so doing this for every UserEventResults in the competition slows
        # down the leaderboards noticeably.
        is_fmc = event_name == FMC
        is_blind = event_name in BLIND_EVENTS
        results.times_string = build_times_string(results.solves, event_format, is_fmc, is_blind)

        # Determine and set if the user set any PBs in this event
        set_pb_flags(user, results, event_id)

    return results


def build_user_solves(solves_data):
    """ Builds and returns a list of UserSolves from the data coming from the front end. """

    user_solves = list()

    for solve in solves_data:

        time = solve[TIME]

        # If the user hasn't recorded a time for this scramble, then just skip to the next
        if not time:
            continue

        # Set the time (in centiseconds), DNF and +2 status, and the scramble ID for this UserSolve
        time        = int(time)
        dnf         = solve[IS_DNF]
        plus_two    = solve[IS_PLUS_TWO]
        scramble_id = solve[SCRAMBLE_ID]

        user_solve = UserSolve(time=time, is_dnf=dnf, is_plus_two=plus_two, scramble_id=scramble_id)
        user_solves.append(user_solve)

    return user_solves


def set_is_complete(user_event_results, event_format, expected_num_solves):
    """ Determine whether this event is considered complete or not. """

    # All blind events are best-of-3, but ranked by single,
    # so consider those complete if there are any solves complete at all
    if event_format == EventFormat.Bo3:
        user_event_results.is_complete = bool(user_event_results.solves)

    # Other events are complete if all solves have been completed
    else:
        user_event_results.is_complete = len(user_event_results.solves) == expected_num_solves


def set_single_and_average(user_event_results, expected_num_solves, event_format):
    """ Determines and sets the best single and average for the UserEventResults. """

    # If not all the solves have been completed, we only know the single
    if len(user_event_results.solves) < expected_num_solves:
        user_event_results.single  = determine_best_single(user_event_results.solves)
        user_event_results.average = ''

    # Otherwise set the single and average if all solves are done
    else:
        single, average = determine_bests(user_event_results.solves, event_format)
        user_event_results.single  = single
        user_event_results.average = average


# -------------------------------------------------------------------------------------------------
#                  Stuff related to processing PBs (personal bests) below
# -------------------------------------------------------------------------------------------------

# Some representations of DNF and <no PBs yet>
# A DNF is a PB if no other PBs have been set, so `PB_DNF` is represented as a really slow time
# that's at faster than `NO_PB_YET`.

PB_DNF    = 88888888  # In centiseconds, this is ~246 hours. Slower than any conceivable real time
NO_PB_YET = 99999999

def __pb_representation(time):
    """ Takes a `time` value from a user solve and converts it into a representation useful for
    determining PBs. If a time is recorded, return the centiseconds, otherwise use the contants
    set above. """

    if time == "DNF":
        return PB_DNF
    elif time == '':
        return NO_PB_YET
    else:
        return int(time)


def set_pb_flags(user, event_result, event_id):
    """ Sets the appropriate flag if either the single or average for this event is a PB. """

    pb_single, pb_average = get_pbs_for_user_and_event_excluding_latest(user.id, event_id)

    event_result.was_pb_single = __pb_representation(event_result.single) < pb_single
    event_result.was_pb_average = __pb_representation(event_result.average) < pb_average

    return event_result


def get_pbs_for_user_and_event_excluding_latest(user_id, event_id):
    """ Returns a tuple of PB single and average for this event for the specified user, except
    for the current comp. Excluding the current comp allows for the user to keep updating their
    results for this comp, and the logic determining if this comp has a PB result doesn't include
    this comp itself. """

    results_with_pb_singles = get_pb_single_event_results_except_current_comp(user_id, event_id)
    singles = [__pb_representation(r.single) for r in results_with_pb_singles]
    pb_single = min(singles) if singles else NO_PB_YET

    results_with_pb_averages = get_pb_average_event_results_except_current_comp(user_id, event_id)
    averages = [__pb_representation(r.average) for r in results_with_pb_averages]
    pb_average = min(averages) if averages else NO_PB_YET

    return pb_single, pb_average
