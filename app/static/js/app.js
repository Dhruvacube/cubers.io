$(function(){

// ---------------------------------------------------------------------------------------------------------------------
// Below is the code related to the competition manager
// ---------------------------------------------------------------------------------------------------------------------

    /**
     * The application which manages the competition, stores times for all competition events, creates timer instances
     */
    var CompManagerApp = {
        timer: null,
        timerPanelTemplate: null,
        summaryPanelTemplate: null,
        
        // this is the events_data object that is rendered into the home page template
        events: window.app.events_data,  

        /**
         * Wires up the events associated with page elements.
         */
        wire_js_events: function() {
            this.wire_event_card_click();
            this.wire_submit_button_click();
        },

        wire_submit_button_click: function() {
            var _appContext = this;

            $('#times-submit>.btn-summary').click(function() {
                var completeEvents = [];
                var incompleteEvents = [];
                $.each(this.events, function(i, event){
                    if (event.status === 'complete') {
                        completeEvents.push(event);
                    } else if (event.status === 'incomplete') {
                        incompleteEvents.push(event);
                    }
                });

                $.ajax({
                    url: "/eventSummaries",
                    type: "POST",
                    data: JSON.stringify(completeEvents),
                    contentType: "application/json",
                    success: function(data) {
                        data = JSON.parse(data);
                        _appContext
                            .show_summary_panel.bind(_appContext)(data, completeEvents, incompleteEvents);
                    },
                });
            }.bind(_appContext));
        },

        show_summary_panel: function(summary_data, complete_events, incomplete_events) {
            $.each(complete_events, function(i, event) {
                event.summary = summary_data[event.comp_event_id];
            });

            $.each(incomplete_events, function(i, event) {
                var solves = [];
                $.each(event.scrambles, function(i, scramble) {
                    if (scramble.time) {
                        var timeStr = "DNF";
                        if (!scramble.isDNF) {
                            timeStr = window.app.convertRawCsForSolveCard(scramble.time, scramble.isPlusTwo);
                        } 
                        solves.push(timeStr);
                    }
                });
                event.summary = "? = " + solves.join(", ");
            });

            var logged_in_with_any_solves = (window.app.user_logged_in && (complete_events.length > 0 || incomplete_events.length > 0));
            var show_submit_button = (complete_events.length > 0 || logged_in_with_any_solves);

            var data = {
                logged_in: window.app.user_logged_in,
                comp_title: $('#eventsPanelDataContainer').data('compname'),
                complete_events: complete_events,
                incomplete_events: incomplete_events,
                show_submit_button: show_submit_button,
                no_solves: (complete_events.length == 0 && incomplete_events.length == 0),
            };

            var $summaryDiv  = $('#summary_panel');
            var $eventsDiv = $('#event_list_panel');

            // Render the Handlebars template for the summary panel, and set it as
            // the new html for the summary panel div
            $summaryDiv.html($(this.summaryPanelTemplate(data)));

            // Hide the events panel and show the summary panel
            $eventsDiv.ultraHide(); $summaryDiv.ultraShow();

            this.wire_return_to_events_from_summary();
            this.wire_submit_button();
        },

        /**
         * 
         */
        wire_return_to_events_from_summary: function() {
            $('#summary-buttons>.btn-return').click(function(e){
                // hide the summary panel and show the events panel
                var $summaryDiv  = $('#summary_panel');
                var $eventsDiv = $('#event_list_panel');
                $summaryDiv.ultraHide(); $eventsDiv.ultraShow();
            });
        },

        /**
         * 
         */
        wire_submit_button: function() {
            var _appContext = this;
            $('#summary-buttons>.btn-submit').click(function(e){
                $("#input-results").val(JSON.stringify(_appContext.events));
                $("#form-results").submit();
            });
        },

        /**
         * When clicking on an event card, shows the timer panel for the selected event
         */
        wire_event_card_click: function() {
            $('.event-card').click(function(e) {
                var $event = $(e.target).closest('.event-card');
                this.show_timer_for_event($event);
            }.bind(this));
        },

        /**
         * When clicking the button to return to the events panel, store complete solve times,
         * update the card for the current event to the correct state, then hide the timer panel
         * and show the events panel
         */
        wire_return_to_events_from_timer: function() {
            var _this = this;
            $('#return-to-events>.btn-return').click(function(e){
                
                kd.SPACE.unbindUp(); kd.SPACE.unbindDown();

                var compEventId = $('#timer_panel .timerEventDataContainer').data('compeventid');
                var totalSolves = $('#timer_panel .timerEventDataContainer').data('totalsolves');

                // iterate through each completed solve, grab the scramble ID and raw solve time
                // in centiseconds, and set the solve time for that scramble in the events data object
                $('.single-time.complete').each(function(i){
                    
                    // need to read rawTimeCentiseconds via attr rather than data, since
                    // we create and set that data attribute after the DOM was built
                    var solveCs = parseInt($(this).attr("data-rawTimeCentiseconds"));
                    var isDNF = window.app.evaluateBool($(this).attr("data-isDNF"));
                    var isPlusTwo = window.app.evaluateBool($(this).attr("data-isPlusTwo"));
                    var scrambleId = $(this).data('id');

                    $.each(_this.events[compEventId].scrambles, function(j, currScramble) {
                        if( currScramble.id != scrambleId ){ return true; }
                        currScramble.time = solveCs;
                        currScramble.isDNF = isDNF;
                        currScramble.isPlusTwo = isPlusTwo;
                        return false;
                    })
                });

                var comment = $('#comment_'+compEventId).val();
                _this.events[compEventId].comment = comment;

                // hide the timer panel and show the events panel
                var $timerDiv  = $('#timer_panel');
                var $eventsDiv = $('#event_list_panel');
                $timerDiv.ultraHide(); $eventsDiv.ultraShow();

                // if the number of complete solves matches the total number of scrambles
                // for this event, mark it as complete
                var completedSolves = $('.single-time.complete').length;
                if (completedSolves == totalSolves) {
                    $('#event-'+compEventId).removeClass('incomplete').addClass('complete');
                    _this.events[compEventId].status = 'complete';
                } else if (completedSolves > 0) {
                    $('#event-'+compEventId).removeClass('complete').addClass('incomplete');
                    _this.events[compEventId].status = 'incomplete';
                } else {
                    $('#event-'+compEventId).removeClass('complete incomplete');
                    _this.events[compEventId].status = 'unstarted;';
                }
            });
        },

        /**
         * Aggregate all the necessary event-related data, use it to render a new timer panel,
         * and then hide the events panel and show the timer panel
         */
        show_timer_for_event: function($selected_event) {
            var comp_event_id = $selected_event.data('comp_event_id');
            var data = {
                comp_event_id : comp_event_id,
                event_id      : $selected_event.data('event_id'),
                event_name    : $selected_event.data('event_name'),
                scrambles     : this.events[comp_event_id]['scrambles'],
                total_solves  : this.events[comp_event_id]['scrambles'].length,
                comment       : this.events[comp_event_id].comment,
            };

            // FMC requires manual entry of integer times, and no timer
            // Gotta do something completely different
            if (data.event_name === 'FMC') {
                data.isFMC = true;
                this.show_entry_for_fmc(data);
                return
            }
            
            var $timerDiv  = $('#timer_panel');
            var $eventsDiv = $('#event_list_panel');

            // Render the Handlebars tempalte for the timer panel with the event-related data
            // collected above, and set it as the new html for the timer panel div
            $timerDiv.html($(this.timerPanelTemplate(data)));
            
            // Hide the events panel and show the timer panel
            $eventsDiv.ultraHide(); $timerDiv.ultraShow();

            // Determine the first solve/scramble that should be attached to the timer,
            // set it as active, and attach it. If all solves are already complete (because
            // the user is returning to this event after completing them, for whatever reason)
            // then don't attach the timer. Otherwise, choose the first incomplete solve.
            if ($('.single-time:not(.complete)').length != 0) {
                var $firstSolveToAttach = $('.single-time:not(.complete)').first();
                window.app.timer.attachToScramble(parseInt($firstSolveToAttach.attr("data-id")));
                //this.prepare_timer_for_start();
            }
            
            // Adjust the font size for the current scramble to make sure it's as large
            // as possible and still fits in the scramble area
            fitty('.scramble-wrapper>div', {minSize: 18, maxSize: 24});

            // Wire the solve card and return button events, and get the timer ready to go
            this.wire_return_to_events_from_timer();
            this.wire_solve_context_menu();
        },

        /**
         * 
         */
        show_entry_for_fmc: function(data) {
            var $timerDiv  = $('#timer_panel');
            var $eventsDiv = $('#event_list_panel');

            // Render the Handlebars tempalte for the timer panel with the event-related data
            // collected above, and set it as the new html for the timer panel div
            $timerDiv.html($(this.timerPanelTemplate(data)));
            
            // Hide the events panel and show the timer panel
            $eventsDiv.ultraHide(); $timerDiv.ultraShow();

            // swallow tab key, prevent tabbing into next contenteditable div
            $(".single-time.fmc>.time-value").keydown(function (e) {
                var code = (e.keyCode ? e.keyCode : e.which);
                if (code == 9) {
                    e.preventDefault();
                    return;
                }
            });

            // integers only, and update complete status and raw "time" attribute
            $(".single-time.fmc>.time-value").on("keypress keyup blur",function (e) {
                $(this).val($(this).text().replace(/[^\d].+/, ""));
                if (parseInt($(this).text()) > 0) {
                   $(this).parent().addClass('complete');
                   $(this).parent().attr("data-rawTimeCentiseconds", parseInt($(this).text()));
                } else {
                   $(this).parent().removeClass('complete'); 
                   $(this).parent().attr("data-rawTimeCentiseconds", null);
                }
                if ((e.which < 48 || e.which > 57)) {
                    e.preventDefault();
                }
            });

            $(".single-time.fmc").click(function(){

                $('.single-time.active').removeClass('active');
                $(this).addClass('active');

                var newScramble = $(this).data('scramble');

                var renderedScramble = "";
                $.each(newScramble.split('\n'), function(i, piece){
                    renderedScramble += "<p>" + piece + "</p>";
                });

                var $scrambleHolder = $('.scramble-wrapper>div');
                $scrambleHolder.html(renderedScramble);
            });

            this.wire_return_to_events_from_timer();
        },

        /**
         * Wire up the left-click context menu on each solve card for adding and removing
         * solve penalties (DNF, +2), and retrying a solve.
         */
        wire_solve_context_menu: function() {
            var _appContext = this;

            // Clear all the penalties, set visible time back to the time of the solve
            var clearPenalty = function($solveClicked) {
                $solveClicked.attr('data-isPlusTwo', 'false');
                $solveClicked.attr('data-isDNF', 'false');

                var cs = parseInt($solveClicked.attr("data-rawTimeCentiseconds"));
                $solveClicked.find('.time-value').html(window.app.convertRawCsForSolveCard(cs));
            };

            // Add DNF penalty, set visible time to 'DNF'
            var setDNF = function($solveClicked) {
                $solveClicked.attr('data-isPlusTwo', 'false');
                $solveClicked.attr('data-isDNF', 'true');
                $solveClicked.find('.time-value').html("DNF");
            }

            // Add +2 penalty, set visible time to actual time + 2 seconds, and "+" mark to indicate penalty
            var setPlusTwo = function($solveClicked) {
                $solveClicked.attr('data-isPlusTwo', 'true');
                $solveClicked.attr('data-isDNF', 'false');

                var cs = parseInt($solveClicked.attr("data-rawTimeCentiseconds"));
                $solveClicked.find('.time-value').html(window.app.convertRawCsForSolveCard(cs + 200) + "+");
            }

            // Check if the selected solve is complete
            var isComplete = function($solveClicked) { return $solveClicked.hasClass('complete'); }

            // Check if the selected solve has DNF penalty
            var hasDNF = function($solveClicked) { return window.app.evaluateBool($solveClicked.attr('data-isDNF')); }

            // Check if the selected solve has +2 penalty
            var hasPlusTwo = function($solveClicked) { return window.app.evaluateBool($solveClicked.attr('data-isPlusTwo')); }     

            // Retry the selected solve - set it as the only active solve, attach the timer, prepare the timer
            var retrySolve = function($solveClicked) {
                // Remove active status from whichever solve is currently active, if any.
                // Set the selected solve as active.
                $('.single-time.active').removeClass('active');
                $solveClicked.addClass('active');

                // Reset the timer, and attach it to this solve card
                window.app.timer.reset();
                window.app.timer.attachToScramble(parseInt($solveClicked.attr("data-id")));

                // Wait a beat then attempt to prepare the timer for the user to start it
                //setTimeout(_appContext.enable.bind(_appContext), 200);
            }

            $.contextMenu({
                selector: '.single-time:not(.fmc)',
                trigger: 'left',
                hideOnSecondTrigger: true,
                items: {
                    "clear": {
                        name: "Clear penalty",
                        icon: "far fa-thumbs-up",
                        callback: function(itemKey, opt, e) { clearPenalty($(opt.$trigger)); },
                        disabled: function(key, opt) { return !(hasDNF(this) || hasPlusTwo(this)); }
                    },
                    "dnf": {
                        name: "DNF",
                        icon: "fas fa-ban",
                        callback: function(itemKey, opt, e) { setDNF($(opt.$trigger)); },
                        disabled: function(key, opt) { return !(isComplete(this) && !hasDNF(this)); }
                    },
                    "+2": {
                        name: "+2",
                        icon: "fas fa-plus",
                        callback: function(itemKey, opt, e) { setPlusTwo($(opt.$trigger)); },
                        disabled: function(key, opt) { return !(isComplete(this) && !hasPlusTwo(this)); }
                    },
                    "sep1": "---------",
                    "retry": {
                        name: "Redo solve",
                        icon: "fas fa-redo",
                        callback: function(itemKey, opt, e) { retrySolve($(opt.$trigger)); },
                        disabled: function(key, opt) { return !isComplete(this) }
                    },
                }
            });
        },

        /**
         * Automatically advances the timer to the next incomplete solve.
         */
        auto_advance_timer_scramble: function() {
            // if there are no more incomplete solves, bail out early without doing anything
            var $incompletes = $('.single-time:not(.complete)');
            if ($incompletes.length === 0) { return; }

            // otherwise attach the timer to the first incomplete solve and prepare the timer
            // to start
            var $firstIncomplete = $incompletes.first();
            window.app.timer.attachToScramble(parseInt($firstIncomplete.attr("data-id")));
            setTimeout(this.prepare_timer_for_start.bind(this), 200);
        },

        update_events_completeness_status: function() {
            $.each(this.events, function(i, event){
                var totalSolves = 0;
                var completeSolves = 0;
                $.each(event.scrambles, function(j, scramble){
                    totalSolves += 1;
                    if (scramble.time) { completeSolves += 1; }
                });
                if (totalSolves == completeSolves) {
                    $('#event-'+event.comp_event_id).addClass('complete');
                    event.status = 'complete';
                } else if (completeSolves > 0) {
                    $('#event-'+event.comp_event_id).addClass('incomplete');
                    event.status = 'incomplete';
                }
            });
        },

        /**
         * Setup stuff when the competition manager app is initialized
         */
        init: function() {

            this.update_events_completeness_status();
        
            // keydrown.js's keyboard state manager is tick-based
            // this is boilerplate to make sure the kd namespace has a recurring tick
            kd.run(function () { kd.tick(); });

            // wire up all the javascript events we need to handle immediately
            this.wire_js_events();

            // Register Handlebars helper functions to help with rendering timer panel template
            //          inc: increments the supplied integer by 1 and returns
            //           eq: compares two values for equality and returns the result
            // convertRawCs: returns a user-friendly representation of the supplied centiseconds
            Handlebars.registerHelper("inc", function(value, options){ return parseInt(value) + 1; });
            Handlebars.registerHelper("eq", function(a, b, options){ return a == b; });
            Handlebars.registerHelper("renderTime", window.app.renderTime);

            // Compile the Handlebars template for the timer panel and summary panel
            // and store the renderers so we can render them later
            this.timerPanelTemplate = Handlebars.compile($('#timer-template').html());
            this.summaryPanelTemplate = Handlebars.compile($('#summary-template').html());
        },
    };

    // Let's get this party started!
    CompManagerApp.init();
});