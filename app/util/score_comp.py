""" Business logic for reading comments in a competition's Reddit thread, parsing submissions,
scoring users, and posting the results. """

import re
from time import sleep

from app.persistence.comp_manager import get_active_competition, get_competition, save_competition
from app.util.reddit_util import get_submission_with_id, submit_competition_post,\
get_permalink_for_comp_thread, update_results_thread
from app.util.times_util import convert_seconds_to_friendly_time

# -------------------------------------------------------------------------------------------------

# It's actually 40k characters, but let's bump it back a smidge to have a little breathing room
MAX_REDDIT_THREAD_LENGTH = 39500

# -------------------------------------------------------------------------------------------------

def filter_no_author(entries):
    """ Returns a filtered list of competition entries (which here are PRAW Comments) which do not
    contain any author=None.  """

    return [e for e in entries if e.author is not None]


def filter_entries_with_no_events(entries, event_names):
    """ Returns a filtered list of competition entries (which here are PRAW Comments) which do
    not mention any events from the competition. """

    return [e for e in entries if find_events(e, event_names)]


def filter_entries_that_are_wip(entries):
    """ Returns a filtered list of competition entries (which here are PRAW Comments) which have any
    of the work-in-progress magic phrases. """

    return [e for e in entries if ("WIP" not in e.body) and ("FORMATTINGADVICE" not in e.body)]

# -------------------------------------------------------------------------------------------------

def score_previous_competition(is_rerun=False, comp_id=None):
    """ Score the previous competition and post the results. """

    # TODO: comment more thoroughly below

    # Get the reddit thread ID and the competition model for the competition to be scored
    if comp_id:
        competition_being_scored = get_competition(comp_id)
    else:
        competition_being_scored = get_active_competition()

    submission_id = competition_being_scored.reddit_thread_id

    # Build a list of event names that were in this competition
    event_names = [comp_event.Event.name for comp_event in competition_being_scored.events]

    # Get the PRAW Submission object and make sure we have all the top-level comments
    submission = get_submission_with_id(submission_id)
    try_count = 0
    while try_count < 10:
        try_count += 1
        try:
            submission.comments.replace_more()
            break
        except:
            sleep(5)
    entries = submission.comments

    # Filter out all the entry comments we don't want
    entries = filter_no_author(entries)
    entries = filter_entries_with_no_events(entries, event_names)
    entries = filter_entries_that_are_wip(entries)

    # TODO: BLACKLIST - filter events from user entries if that event is blacklisted
    # aka the userEventResults for this comp, user, and is blacklisted

    # Create a competitor record for each entry
    competitors = [Competitor(entry) for entry in entries]

    # Creating a competitor record automatically removes any broken times/events
    # Filter out any competitors without any events left
    competitors = [c for c in competitors if c.events]

    # Remove duplicate users
    competitors = list(set(competitors))

    # Build up a dictionary of event name to participant list
    # Participant list contains tuple of (username, event result), sorted by event result
    comp_event_results = dict()
    for event_name in event_names:
        participating_users = list()
        for competitor in competitors:
            if event_name in competitor.events:
                time = competitor.event_time_map[event_name]
                participating_users.append((competitor.name, float(time), competitor))
        if not participating_users:
            continue
        participating_users.sort(key=lambda x: x[1])
        num_event_participants = len(participating_users)
        for i, record in enumerate(participating_users):
            record[2].points += (num_event_participants - (i+1) + 1)
        comp_event_results[event_name] = participating_users

    permalink  = get_permalink_for_comp_thread(submission_id)
    comp_title = competition_being_scored.title
    post_body = 'Results for [{}]({})'.format(comp_title, permalink)
    event_chunks = list()

    for event_name in event_names:
        event_chunk_txt = ''
        if not event_name in comp_event_results.keys():
            continue
        participants = comp_event_results[event_name]
        if not participants:
            continue
        event_chunk_txt += '\n\n**{}**\n\n'.format(event_name)
        for participant in participants:
            time = participant[1]
            if event_name != 'FMC':
                time = convert_seconds_to_friendly_time(time)
            event_chunk_txt += '1. {}: {}\n\n'.format(participant[0], time)
        event_chunks.append([event_name, event_chunk_txt])

    overall_txt = ''
    overall_txt += '---\n\n**Total points this week**'
    overall_txt += '\n\nEach event gives `# of participants - place + 1` points\n\n'
    competitors.sort(key=lambda c: c.points, reverse=True)
    for competitor in competitors:
        overall_txt += '1. {}: {}\n\n'.format(competitor.name, competitor.points)

    skipped_event_names = list()
    while event_chunks:
        chunk = event_chunks.pop(0)
        if len(post_body) + len(overall_txt) + len(chunk[1]) < MAX_REDDIT_THREAD_LENGTH:
            post_body += chunk[1]
        else:
            skipped_event_names.append(chunk[0])

    if skipped_event_names:
        post_body += '\n\n**Note: Results for the following events were not included here, '
        post_body += "to allow this post to fit within Reddit's maximum post length:**\n\n"
        for name in skipped_event_names:
            post_body += '1. {}\n\n'.format(name)

    post_body += overall_txt

    title = 'Results for {}'.format(competition_being_scored.title)

    if not is_rerun:
        new_post_id = submit_competition_post(title, post_body)
        competition_being_scored.result_thread_id = new_post_id
        save_competition(competition_being_scored)
    else:
        results_thread_id = competition_being_scored.result_thread_id
        update_results_thread(post_body, results_thread_id)


def find_events(comment, events):
    """ Returns a list of events that are present in this comment. """
    return [e for e in events if '{}:'.format(e) in comment.body]

# -------------------------------------------------------------------------------------------------

class Competitor:
    """ Encapsulates a Competitor (who posts a Reddit comment to the competition thread), and the
    information relating to their submission (times, events participated in, etc). """

    def __init__(self, entry):
        parse_results = parse(entry.body)
        self.events = parse_results[1]
        self.times = parse_results[0]
        self.name = '/u/{}'.format(entry.author.name)
        self.points = 0
        self.fix_times()
        self.event_time_map = dict(zip(self.events, self.times))

    def fix_times(self):
        """ Remove the entries in the events and times lists where the entry is 'Error' """
        while 'Error' in self.times:
            self.events.pop(self.times.index('Error'))
            self.times.pop(self.times.index("Error"))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name == other.name
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def __ne__(self, other):
        return not self.__eq__(other)

# -------------------------------------------------------------------------------------------------
#   This is pretty awful below, but it's functional so let's mess with it as little as possible!
#   Just minor tweaks to improve readibility
# -------------------------------------------------------------------------------------------------

def parse(post):
    """ Parse a comment body to extract the user's submitted times and events information. """

    # As as long as a line of text "fits" this pattern, we will get a successful match.
    # Otherwise we get 'None'.
    matcher = re.compile('^(.+?)\\:\\s*([^\\s]+).*')

    # Create a second matcher to find "empty" results.
    # ONLY apply it if the first rule didn't match. (see below)
    dnf_matcher = re.compile('^([^\\:\\s]+)\\s*\\:.*')

    times = list()
    events = list()
    raw_times = list()

    # Split our post into individual lines, and process them
    for line in post.splitlines():
        # Now replace any * characters with nothing.
        content = re.sub ('\\*','',line)

        # Use our matchers to see if the current line matches our pattern(s).
        result = matcher.match(content)
        dnf_result = dnf_matcher.match(content)

        average = ''
        if result is not None:
            # We have gotten a puzzle name and an average.
            if result.group(1).lower() == "mirror blocks":
                events.append("3x3 Mirror Blocks/Bump")
            elif result.group(1).lower() == "3x3 mirror blocks/bump":
                events.append("3x3 Mirror Blocks/Bump")
            elif result.group(1).lower() == "3x3 relay":
                events.append("3x3 Relay of 3")
            elif result.group(1).lower() == "relay of 3":
                events.append("3x3 Relay of 3")
            elif result.group(1).lower() == "5x5x5":
                events.append("5x5")
            elif result.group(1).lower() == "6x6x6":
                events.append("6x6")
            elif result.group(1).lower() == "7x7x7":
                events.append("7x7")
            elif result.group(1).lower() == "4x4oh":
                events.append("4x4 OH")
            elif result.group(1).lower() == "pyra":
                events.append("Pyraminx")
            elif result.group(1).lower() == "blind":
                events.append("3BLD")
            elif result.group(1).lower() == "4x4oh":
                events.append("4x4 OH")
            elif result.group(1).lower() == "f2l":
                events.append("F2L")
            elif result.group(1).lower() == "bld":
                events.append("3BLD")
            elif result.group(1).lower() == "pll time attack":
                events.append("PLL Time Attack")
            elif result.group(1).lower() == "3x3 mirror blocks/bump":
                events.append("3x3 Mirror Blocks/Bump")
            elif result.group(1).lower() == "3x3 mirror blocks":
                events.append("3x3 Mirror Blocks/Bump")
            elif result.group(1).lower() == "mirror blocks/bump":
                events.append("3x3 Mirror Blocks/Bump")
            elif result.group(1).lower() == "3x3 with feet":
                events.append("3x3 With Feet")
            elif result.group(1).lower() == "3x3 oh":
                events.append("3x3OH")
            elif result.group(1).lower() == "oll":
                events.append("OH OLL")
            else:
                events.append(result.group(1))

            average = result.group(2)   #The second group was average.
            if ":" in average:
                try:
                    mins = (int)(average[0: average.index(":")])
                    secs = (int)(average[average.index(":") + 1: average.index(".")])
                    dec = (int)(average[average.index(".") + 1: average.index(".") + 3])

                    secs += mins * 60
                    if dec < 10:
                        average = str(secs) + ".0" + str(dec)
                    else:
                        average = str(secs) + "." + str(dec)
                except ValueError:
                    average = "Error"

            try:
                float(re.sub('[* ()=/]', '', average).strip())
                times.append(re.sub('[* ()=/]', '', average).strip())
            except:
                times.append("Error")

        elif dnf_result is not None:
            # We have a puzzle name, but no average.
            events.append(dnf_result.group(1))
            times.append("Error")

        else:
            # If a line didn't match any of the two rules, skip it.
            continue
    return [times, events, raw_times]
