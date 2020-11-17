#!/usr/bin/env python

"""The data structures to store a schedule (task system), along with all
the job releases and other events that have occurred for each task. This gives
a high-level representation of a schedule that can be converted to, say, a
graphic."""

from graph import *
import util

import copy

EVENT_LIST = None
SPAN_EVENTS = None

class TimeSlotArray(object):
    """Represents another way of organizing the events. This structure organizes events by
    the (approximate) time at which they occur. Events that occur at approximately the same
    time are assigned the same ``slot'', and each slot organizes its events by task number
    as well as by CPU."""

    TASK_LIST = 0
    CPU_LIST = 1

    def __init__(self, time_per_maj=None, num_tasks=0, num_cpus=0):
        if time_per_maj is None:
            self.array = None
            return

        self.time_per_maj = time_per_maj
        self.list_sizes = { TimeSlotArray.TASK_LIST : num_tasks, TimeSlotArray.CPU_LIST : num_cpus }
        self.array = {}

        for type in self.list_sizes:
            num = self.list_sizes[type]
            self.array[type] = []
            for j in range(0, num):
                # for each slot in the array, we need a list of all events under this type
                # (for example, a list of all events that occur in this time slot, indexed
                # by task).
                self.array[type].append(dict(zip(EVENT_LIST, \
                                [{} for j in range(0, len(EVENT_LIST))])))

    def get_time_slot(self, time):
        return int(time // self.time_per_maj)

    def _put_event_in_slot(self, list_type, no, klass, slot, event):
        if slot not in self.array[list_type][no][klass]:
            self.array[list_type][no][klass][slot] = []
        self.array[list_type][no][klass][slot].append(event)

    def add_event_to_time_slot(self, event):
        task_no = event.get_job().get_task().get_task_no()
        cpu = event.get_cpu()
        time_slot = self.get_time_slot(event.get_time())

        self._put_event_in_slot(TimeSlotArray.TASK_LIST, task_no, event.__class__, time_slot, event)
        self._put_event_in_slot(TimeSlotArray.CPU_LIST, cpu, event.__class__, time_slot, event)

        if event.__class__ in SPAN_END_EVENTS:
            self.fill_span_event_from_end(event)

    def fill_span_event_from_end(self, event):
        start_slot = None
        if event.corresp_start_event is None:
            start_slot = self.get_time_slot(event.get_job().get_task().get_schedule().start) - 1
        else:
            start_slot = self.get_time_slot(event.corresp_start_event.get_time())
        end_slot = self.get_time_slot(event.get_time())

        for slot in range(start_slot + 1, end_slot):
            task_no = event.get_job().get_task().get_task_no()
            cpu = event.get_cpu()

            dummy = SPAN_END_EVENTS[event.__class__](task_no, cpu)
            dummy.corresp_start_event = event.corresp_start_event
            dummy.corresp_end_event = event

            self._put_event_in_slot(TimeSlotArray.TASK_LIST, task_no, dummy.__class__, slot, dummy)
            self._put_event_in_slot(TimeSlotArray.CPU_LIST, cpu, dummy.__class__, slot, dummy)

    def fill_span_event_from_start(self, event):
        end_slot = None
        if event.corresp_end_event is None:
            end_slot = self.get_time_slot(event.get_job().get_task().get_schedule().end) + 1
        else:
            end_slot = self.get_time_slot(event.corresp_end_event.get_time())
        start_slot = self.get_time_slot(event.get_time())

        for slot in range(start_slot + 1, end_slot):
            task_no = event.get_job().get_task().get_task_no()
            cpu = event.get_cpu()

            dummy = SPAN_START_EVENTS[event.__class__](task_no, cpu)
            dummy.corresp_start_event = event
            dummy.corresp_end_event = event.corresp_end_event

            self._put_event_in_slot(TimeSlotArray.TASK_LIST, task_no, dummy.__class__, slot, dummy)
            self._put_event_in_slot(TimeSlotArray.CPU_LIST, cpu, dummy.__class__, slot, dummy)

    def get_events(self, slots, list_type, event_types):
        for type in event_types:
            for slot in slots:
                for no in slots[slot]:
                    if slot in self.array[list_type][no][type]:
                        for event in self.array[list_type][no][type][slot]:
                            yield event

    def get_slots(self, slots, start, end, start_no, end_no, list_type):
        if self.array is None:
            return # empty schedule

        if start > end:
            raise ValueError('Litmus is not a time machine')
        if start_no > end_no:
            raise ValueError('start no should be less than end no')

        start_slot = self.get_time_slot(start)
        end_slot = self.get_time_slot(end) + 1
        start_no = max(0, start_no)
        end_no = min(self.list_sizes[list_type] - 1, end_no)

        for slot in xrange(start_slot, end_slot + 1):
            if slot not in slots:
                slots[slot] = {}
            for no in xrange(start_no, end_no + 1):
                slots[slot][no] = None

class Schedule(object):
    """The total schedule (task system), consisting of a certain number of
    tasks."""

    def __init__(self, name, num_cpus, task_list=[]):
        self.name = name
        self.tasks = {}
        self.task_list = []
        self.selected = {}
        self.time_slot_array = None
        self.cur_task_no = 0
        self.num_cpus = num_cpus
        self.jobless = []
        for task in task_list:
            self.add_task(task)

    def get_selected(self):
        return self.selected

    def set_selected(self, selected):
        self.selected = selected

    def add_selected(self, selected):
        for layer in selected:
            if layer not in self.selected:
                self.selected[layer] = {}
            for event in selected[layer]:
                if event not in self.selected:
                    self.selected[layer][event] = {}
                for graph in selected[layer][event]:
                    self.selected[layer][event][graph] = selected[layer][event][graph]

    def remove_selected(self, selected):
        for layer in selected:
            if layer in self.selected:
                for event in selected[layer]:
                    if event in self.selected[layer]:
                        del self.selected[layer][event]

    def set_time_params(self, time_per_maj=None):
        self.time_per_maj = time_per_maj
        if self.time_per_maj is None:
            self.time_slot_array = TimeSlotArray()
            return

        self.time_slot_array = TimeSlotArray(self.time_per_maj, \
                                                 len(self.task_list), self.num_cpus)

    def get_time_slot_array(self):
        return self.time_slot_array

    def get_time_bounds(self):
        return (self.start, self.end)

    def scan(self, time_per_maj):
        self.start = None
        self.end = None

        self.set_time_params(time_per_maj)

        # we scan the graph task by task, and job by job
        for task_no, task in enumerate(self.get_task_list()):
            switches = {}
            for event in EVENT_LIST:
                switches[event] = None
            cur_cpu = [Event.NO_CPU]
            for job_no in sorted(task.get_jobs().keys()):
                job = task.get_jobs()[job_no]
                for event_time in sorted(job.get_events().keys()):
                    # could have multiple events at the same time (unlikely but possible)
                    for event in job.get_events()[event_time]:
                        event.scan(cur_cpu, switches)

            # What if one of the initial "span events" (switch to or inversion starting) never got a
            # corresponding end event? Well, then we assume that the end event was simply outside of
            # the range of whatever we read in. So we need to fill dummies starting from the initial
            # event all the way to the end of the graph, so that the renderer can see the event no matter
            # how far the user scrolls to the right.
            for span_event in SPAN_START_EVENTS:
                event = switches[span_event]
                if event is not None:
                    self.time_slot_array.fill_span_event_from_start(event)

    def add_task(self, task):
        if task.name in self.tasks:
            raise ValueError("task already in list!")
        self.tasks[task.name] = task
        self.task_list.append(task)
        task.schedule = self
        task.task_no = self.cur_task_no
        self.cur_task_no += 1

    def add_jobless(self, event):
        self.jobless.append(event)

    def sort_task_nos_numeric(self):
        # sort task numbers by the numeric value of the task names.
        nums = []

        for task_name in self.tasks:
            nums.append((int(task_name), task_name))

        nums.sort(key=lambda t: t[0])
        for no, task in enumerate(nums):
            self.tasks[task[1]].task_no = no

    def get_jobless(self):
        return self.jobless

    def get_tasks(self):
        return self.tasks

    def get_task_list(self):
        return self.task_list

    def get_name(self):
        return self.name

    def get_num_cpus(self):
        return self.num_cpus

def deepcopy_selected(selected):
    selected_copy = {}
    for layer in selected:
        selected_copy[layer] = copy.copy(selected[layer])
    return selected_copy

class Task(object):
    """Represents a task, including the set of jobs that were run under
    this task."""

    def __init__(self, name, job_list=[]):
        self.name = name
        self.jobs = {}
        self.task_no = None
        self.schedule = None
        for job in job_list:
            self.add_job(job)

    def add_job(self, job):
        if job.job_no in self.jobs:
            raise ScheduleError("a job is already being released at this time for this task")
        self.jobs[job.job_no] = job
        job.task = self

    def get_schedule(self):
        return self.schedule

    def get_jobs(self):
        return self.jobs

    def get_task_no(self):
        return self.task_no

    def get_name(self):
        return self.name

class Job(object):
    """Represents a job, including everything that happens related to the job"""
    def __init__(self, job_no, event_list=[]):
        self.job_no = job_no
        self.events = {}
        self.task = None
        for event in event_list:
            self.add_event(event)

    def add_event(self, event):
        if event.time not in self.events:
            self.events[event.time] = []
        self.events[event.time].append(event)
        event.job = self

    def get_events(self):
        return self.events

    def get_task(self):
        return self.task

    def get_job_no(self):
        return self.job_no

class DummyEvent(object):
    """Represents some event that occurs, but might not actually be
    a full-fledged ``event'' in the schedule. It might instead be a dummy
    event added by the application to speed things up or keep track of
    something. Such an event won't be added to the schedule tree, but
    might appear in the time slot array."""
    def __init__(self, time, cpu):
        self.time = time
        self.cpu = cpu
        self.job = None
        self.layer = None
        self.saved_schedule = None

    def __str__(self):
        return '[Dummy Event]'

    def get_time(self):
        return self.time

    def get_cpu(self):
        return self.cpu

    # Refactor, shouldn't depend on job
    def get_schedule(self):
        if self.saved_schedule is not None:
            return self.saved_schedule
        elif self.get_task() is not None:
            return self.get_task().get_schedule()
        else:
            return None

    # Needed for events not assigned to specific tasks
    def set_schedule(self, schedule):
        self.saved_schedule = schedule

    def get_task(self):
        if self.get_job() is not None:
            return self.get_job().get_task()
        else:
            return None

    def get_job(self):
        return self.job

    def get_layer(self):
        return self.layer

    def render(self, graph, layer, prev_events, selectable=False):
        """Method that the visualizer calls to tell the event to render itself
        Obviously only implemented by subclasses (actual event types)

        ``Rendering'' can mean either actually drawing the event or just
        adding it as a selectable region. This is controlled by the
        ``selectable'' parameter"""
        raise NotImplementdError

class Event(DummyEvent):
    """Represents an event that occurs while a job is running (e.g. get scheduled
    on a CPU, block, ...)"""
    NO_CPU = -1
    NUM_DEC_PLACES = 2

    def __init__(self, time, cpu):
        super(Event, self).__init__(time, cpu)
        self.erroneous = False

    def get_name(self):
        raise NotImplementedError

    def __str__(self):
        return self.get_name() + self._common_str() + ', TIME=' + util.format_float(self.get_time(), Event.NUM_DEC_PLACES)

    def str_long(self, unit):
        if self.get_job() is not None:
            """Prints the event as a string, in ``long'' form."""
            return 'Event Information\n-----------------\n' + \
                    'Event Type: ' + self.get_name() + \
                    '\nTask Name: ' + str(self.get_job().get_task().get_name()) + \
                    '\n(Task no., Job no.): ' + str((self.get_job().get_task().get_task_no(), \
                                                    self.get_job().get_job_no())) + \
                    '\nCPU: ' + str(self.get_cpu()) + \
                    '\nTime: ' + _format_time(self.get_time(), unit) + \
                    '\n\n' + self.get_job().str_long(unit)
        else:
            """Prints the event as a string, in ``long'' form."""
            return 'Event Information\n-----------------\n' + \
                    'Event Type: ' + self.get_name() + \
                    '\nTask Name: None' + \
                    '\nCPU: ' + str(self.get_cpu()) + \
                    '\nTime: ' + _format_time(self.get_time(), unit)

    def _common_str(self):
        if self.get_job() is not None:
            job = self.get_job()
            task = job.get_task()
            return ' for task ' + str(task.get_name()) + ': (TASK, JOB)=' + \
                str((task.get_task_no(), job.get_job_no())) + \
                ', CPU=' + str(self.get_cpu())
        else:
            return ', Cpu=' + str(self.get_cpu())

    def is_erroneous(self):
        """An erroneous event is where something with the event is not quite right,
        something significantly wrong that we don't have logical information telling
        us how we should render the event."""
        return self.erroneous

    def is_selected(self):
        """Returns whether the event has been selected by the user. (needed for rendering)"""
        selected = self.get_job().get_task().get_schedule().get_selected()
        return self.get_layer() in selected and self in selected[self.get_layer()]

    def scan(self, cur_cpu, switches):
        """Part of the procedure that walks through all the events and sets
        some parameters that are unknown at first. For instance, a SwitchAwayEvent
        should know when the previous corresponding SwitchToEvent occurred, but
        the data does not tell us this, so we have to figure that out on our own
        by scanning through the events. ``cur_cpu'' gives the current CPU at this
        time in the scan, and ``switches'' gives the last time a certain switch
        (e.g. SwitchToEvent, InversionStartEvent) occurred"""
        time = self.get_time()

        sched = self.get_schedule()

        if sched is not None:
            if sched.start is None or time < sched.start:
                sched.start = time
            if sched.end is None or time > sched.end:
                sched.end = time

            if item_nos is None:
                item_nos = { TimeSlotArray.TASK_LIST : self.get_task().get_task_no(),
                             TimeSlotArray.CPU_LIST : self.get_cpu() }
            sched.get_time_slot_array().add_event_to_time_slot(self, item_nos)

        self.fill_span_event_from_end()

    def fill_span_event_from_start(self):
        """This method exists for events that can ``range'' over a period of time
        (e.g. SwitchAway and SwitchTo). In case a start event is not paired with
        an end event, or vice versa, we want to fill in dummy events to range all
        the way to the beginning or end. Since most events occur only at a specific
        time, this is usually a no-op."""
        pass

    def fill_span_event_from_end(self):
        """The mirror image of the last method."""
        pass

class SpanEvent(Event):
    def __init__(self, time, cpu, dummy_class):
        super(SpanEvent, self).__init__(time, cpu)
        self.dummy_class = dummy_class

class SpanDummy(DummyEvent):
    def __init__(self):
        super(SpanDummy, self).__init__(None, None)

    def get_task(self):
        if self.corresp_start_event is not None:
            return self.corresp_start_event.get_task()
        if self.corresp_end_event is not None:
            return self.corresp_end_event.get_task()
        return None

    def get_schedule(self):
        if self.corresp_start_event is not None:
            return self.corresp_start_event.get_schedule()
        if self.corresp_end_event is not None:
            return self.corresp_end_event.get_schedule()
        return None

class ErrorEvent(Event):
    pass

class SuspendEvent(Event):
    def __init__(self, time, cpu):
        super(SuspendEvent, self).__init__(time, cpu)
        self.layer = Canvas.MIDDLE_LAYER

    def get_name(self):
        return 'Suspend'

    def scan(self, cur_cpu, switches):
        if self.get_cpu() != cur_cpu[0]:
            self.erroneous = True
            #fprint "suspending on a CPU different from the CPU we are on!"
        super(SuspendEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if layer == self.layer:
            prev_events[self] = None
            if selectable:
                graph.add_sel_suspend_triangle_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                                self.get_cpu(), self)
            else:
                graph.draw_suspend_triangle_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                                self.get_cpu(), self.is_selected())


class ResumeEvent(Event):
    def __init__(self, time, cpu):
        super(ResumeEvent, self).__init__(time, cpu)
        self.layer = Canvas.MIDDLE_LAYER

    def get_name(self):
        return 'Resume'

    def scan(self, cur_cpu, switches):
        if cur_cpu[0] != Event.NO_CPU and cur_cpu[0] != self.get_cpu():
            self.erroneous = True
            #print "Resuming when currently scheduled on a CPU, but on a different CPU from the current CPU!"
        super(ResumeEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if layer == self.layer:
            prev_events[self] = None
            if selectable:
                graph.add_sel_resume_triangle_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                                self.get_cpu(), self)
            else:
                graph.draw_resume_triangle_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                               self.get_cpu(), self.is_selected())


class CompleteEvent(Event):
    def __init__(self, time, cpu):
        super(CompleteEvent, self).__init__(time, cpu)
        self.layer = Canvas.TOP_LAYER

    def get_name(self):
        return 'Complete'

    def scan(self, cur_cpu, switches):
        super(CompleteEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if layer == Canvas.TOP_LAYER:
            prev_events[self] = None
            if selectable:
                graph.add_sel_completion_marker_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                                self.get_cpu(), self)
            else:
                graph.draw_completion_marker_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                                 self.get_cpu(), self.is_selected())

class SwitchToEvent(Event):
    def __init__(self, time, cpu):
        super(SwitchToEvent, self).__init__(time, cpu)
        self.layer = Canvas.BOTTOM_LAYER
        self.corresp_end_event = None

    def get_name(self):
        if self.corresp_end_event is None:
            return 'Switch To (w/o Switch Away)'
        else:
            return 'Scheduled'

    def __str__(self):
        if self.corresp_end_event is None:
            return super(SwitchToEvent, self).__str__()
        return self.get_name() + self._common_str() + ', START=' \
               + util.format_float(self.get_time(), Event.NUM_DEC_PLACES) \
               + ', END=' + util.format_float(self.corresp_end_event.get_time(), Event.NUM_DEC_PLACES)

    def str_long(self):
        if self.corresp_end_event is None:
            return super(SwitchToEvent, self).str_long()
        else :
            return 'Event Type: ' + self.get_name() + \
                '\nTask Name: ' + str(self.get_job().get_task().get_name()) + \
                '\n(Task no., Job no.): ' + str((self.get_job().get_task().get_task_no(), \
                                                self.get_job().get_job_no())) + \
                '\nCPU: ' + str(self.get_cpu()) + \
                '\nStart: ' + str(self.get_time()) + \
                '\nEnd: ' + str(self.corresp_end_event.get_time())

    def scan(self, cur_cpu, switches):
        old_cur_cpu = cur_cpu[0]
        cur_cpu[0] = self.get_cpu()
        switches[SwitchToEvent] = self
        self.corresp_end_event = None

        if old_cur_cpu != Event.NO_CPU:
            self.erroneous = True
            #print "currently scheduled somewhere, can't switch to a CPU"

        super(SwitchToEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if layer == self.layer:
            end_time = None
            clip = None
            if self.corresp_end_event is None:
                end_time = self.get_job().get_task().get_schedule().end
                clip = AlignMode.RIGHT
            else:
                end_time = self.corresp_end_event.get_time()

            prev_events[self] = None
            cpu = self.get_cpu()
            task_no = self.get_job().get_task().get_task_no()
            if selectable:
                graph.add_sel_bar_at_time(self.get_time(), end_time,
                                     task_no, cpu, self)
            else:
                graph.draw_bar_at_time(self.get_time(), end_time,
                                   task_no, cpu, self.get_job().get_job_no(),
                                   clip, self.is_selected())

class SwitchAwayEvent(Event):
    def __init__(self, time, cpu):
        super(SwitchAwayEvent, self).__init__(time, cpu)
        self.layer = Canvas.BOTTOM_LAYER
        self.corresp_start_event = None

    def get_name(self):
        if self.corresp_start_event is None:
            return 'Switch Away (w/o Switch To)'
        else:
            return 'Scheduled'

    def __str__(self):
        if self.corresp_start_event is None:
            return super(SwitchAwayEvent, self).__str__()
        return str(self.corresp_start_event)

    def str_long(self):
        if self.corresp_start_event is None:
            return super(SwitchAwayEvent, self).str_long()

        return self.corresp_start_event.str_long()

    def scan(self, cur_cpu, switches):
        old_cur_cpu = cur_cpu[0]

        self.corresp_start_event = switches[SwitchToEvent]

        cur_cpu[0] = Event.NO_CPU
        switches[SwitchToEvent] = None

        if self.corresp_start_event is not None:
            self.corresp_start_event.corresp_end_event = self

        if self.get_cpu() != old_cur_cpu:
            self.erroneous = True
            #print "switching away from a CPU different from the CPU we are currently on"
        if self.corresp_start_event is None:
            self.erroneous = True
            #print "switch away was not matched by a corresponding switch to"
        elif self.get_time() < self.corresp_start_event.get_time():
            self.erroneous = True
            #print "switching away from a processor before we switched to it?!"

        super(SwitchAwayEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if self.corresp_start_event is None:
            # We never found a corresponding start event. In that case, we can assume it lies
            # in some part of the trace that was never read in. So draw a bar starting from
            # the very beginning.
            if layer == self.layer:
                prev_events[self] = None
                cpu = self.get_cpu()
                task_no = self.get_job().get_task().get_task_no()
                start = self.get_job().get_task().get_schedule().start
                if selectable:
                    graph.add_sel_bar_at_time(start, self.get_time(),
                                     task_no, cpu, self)
                else:
                    graph.draw_bar_at_time(start, self.get_time(),
                                   task_no, cpu, self.get_job().get_job_no(),
                                   AlignMode.LEFT, self.is_selected())
        else:
            if self.corresp_start_event in prev_events:
                return # already rendered the bar
            self.corresp_start_event.render(graph, layer, prev_events, selectable)

class ReleaseEvent(Event):
    def __init__(self, time, cpu):
        super(ReleaseEvent, self).__init__(time, cpu)
        self.layer = Canvas.TOP_LAYER

    def get_name(self):
        return 'Release'

    def scan(self, cur_cpu, switches):
        super(ReleaseEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        prev_events[self] = None
        if layer == Canvas.TOP_LAYER:
            if selectable:
                graph.add_sel_release_arrow_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                            self)
            else:
                graph.draw_release_arrow_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                             self.get_job().get_job_no(), self.is_selected())


class DeadlineEvent(Event):
    def __init__(self, time, cpu):
        super(DeadlineEvent, self).__init__(time, cpu)
        self.layer = Canvas.TOP_LAYER

    def get_name(self):
        return 'Deadline'

    def scan(self, cur_cpu, switches):
        super(DeadlineEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        prev_events[self] = None
        if layer == Canvas.TOP_LAYER:
            if selectable:
                graph.add_sel_deadline_arrow_at_time(self.get_time(), self.get_job().get_task().get_task_no(),
                                              self)
            else:
                graph.draw_deadline_arrow_at_time(self.get_time(),
                                                  self.get_job().get_task().get_task_no(),
                                                  self.get_job().get_job_no(), self.is_selected())

class ActionEvent(Event):
    def __init__(self, time, cpu, action):
        super(ActionEvent, self).__init__(time, cpu)
        self.layer = Canvas.TOP_LAYER
        self.action = int(action)

    def get_name(self):
        return 'Action'

    def scan(self, cur_cpu, switches):
        item_nos = { TimeSlotArray.TASK_LIST : self.get_task().get_task_no(),
                     TimeSlotArray.CPU_LIST : TimeSlotArray.POST_ITEM_NO }
        super(ActionEvent, self).scan(cur_cpu, switches, item_nos)

    def render(self, graph, layer, prev_events, selectable=False):
        prev_events[self] = None
        if layer == Canvas.TOP_LAYER:

            # TODO: need a more official way of doing this
            task_no = -1
            job_no  = -1
            if self.get_job() is not None:
                task_no = self.get_job().get_task().get_task_no()
                job_no = self.get_job().get_job_no()

            if selectable:
                graph.add_sel_action_symbol_at_time(self.get_time(), task_no,
                                                    self.get_cpu(), self)
            else:
                graph.draw_action_symbol_at_time(self.get_time(), task_no,
                                                 self.get_cpu(), self.action,
                                                 job_no, self.is_selected())

class InversionStartEvent(ErrorEvent):
    def __init__(self, time):
        super(InversionStartEvent, self).__init__(time, Event.NO_CPU)
        self.layer = Canvas.BOTTOM_LAYER
        self.corresp_end_event = None

    def get_name(self):
        if self.corresp_end_event is None:
            return 'Inversion Start (w/o Inversion End)'
        else:
            return 'Priority Inversion'

    def __str__(self):
        if self.corresp_end_event is None:
            return super(InversionStartEvent, self).__str__()
        return self.get_name() + self._common_str() + ', START=' \
               + util.format_float(self.get_time(), Event.NUM_DEC_PLACES) \
               + ', END=' + util.format_float(self.corresp_end_event.get_time(), Event.NUM_DEC_PLACES)

    def str_long(self):
        if self.corresp_end_event is None:
            return super(InversionStartEvent, self).str_long()
        else :
            return 'Event Type: ' + self.get_name() + \
                '\nTask Name: ' + str(self.get_job().get_task().get_name()) + \
                '\n(Task no., Job no.): ' + str((self.get_job().get_task().get_task_no(), \
                                                self.get_job().get_job_no())) + \
                '\nCPU: ' + str(self.get_cpu()) + \
                '\nStart: ' + str(self.get_time()) + \
                '\nEnd: ' + str(self.corresp_end_event.get_time())

    def scan(self, cur_cpu, switches):
        switches[InversionStartEvent] = self
        self.corresp_end_event = None

        # the corresp_end_event should already be set
        super(InversionStartEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if layer == self.layer:
            end_time = None
            clip = None
            if self.corresp_end_event is None:
                end_time = self.get_job().get_task().get_schedule().end
                clip = AlignMode.RIGHT
            else:
                end_time = self.corresp_end_event.get_time()

            if layer == self.layer:
                prev_events[self] = None
                cpu = self.get_cpu()
                task_no = self.get_job().get_task().get_task_no()
                if selectable:
                    graph.add_sel_mini_bar_at_time(self.get_time(), end_time,
                                     task_no, cpu, self)
                else:
                    graph.draw_mini_bar_at_time(self.get_time(), end_time,
                                     task_no, cpu, self.get_job().get_job_no(),
                                     clip, self.is_selected())


class InversionEndEvent(ErrorEvent):
    def __init__(self, time):
        super(InversionEndEvent, self).__init__(time, Event.NO_CPU)
        self.layer = Canvas.BOTTOM_LAYER
        self.corresp_start_event = None

    def get_name(self):
        if self.corresp_start_event is None:
            return 'Inversion End (w/o Inversion Start)'
        else:
            return 'Priority Inversion'

    def __str__(self):
        if self.corresp_start_event is None:
            return super(InversionEndEvent, self).__str__()

        return str(self.corresp_start_event)

    def str_long(self):
        if self.corresp_start_event is None:
            return super(InversionEndEvent, self).str_long()

        return self.corresp_start_event.str_long()

    def scan(self, cur_cpu, switches):
        self.corresp_start_event = switches[InversionStartEvent]

        cur_cpu[0] = Event.NO_CPU
        switches[InversionStartEvent] = None

        if self.corresp_start_event is not None:
            self.corresp_start_event.corresp_end_event = self

        if self.corresp_start_event is None:
            self.erroneous = True
            #print "inversion end was not matched by a corresponding inversion start"

        super(InversionEndEvent, self).scan(cur_cpu, switches)

    def render(self, graph, layer, prev_events, selectable=False):
        if self.corresp_start_event is None:
            # We never found a corresponding start event. In that case, we can assume it lies
            # in some part of the trace that was never read in. So draw a bar starting from
            # the very beginning.
            if layer == self.layer:
                prev_events[self] = None
                cpu = self.get_cpu()
                task_no = self.get_job().get_task().get_task_no()
                start = self.get_job().get_task().get_schedule().start
                if selectable:
                    graph.add_sel_mini_bar_at_time(start, self.get_time(),
                                     task_no, cpu, self)
                else:
                    graph.draw_mini_bar_at_time(start, self.get_time(),
                                   task_no, cpu, self.get_job().get_job_no(),
                                   AlignMode.LEFT, self.is_selected())
        else:
            if self.corresp_start_event in prev_events:
                return # already rendered the bar
            self.corresp_start_event.render(graph, layer, prev_events, selectable)

class InversionDummy(DummyEvent):
    def __init__(self, time, cpu):
        super(InversionDummy, self).__init__(time, Event.NO_CPU)
        self.layer = Canvas.BOTTOM_LAYER

    def render(self, graph, layer, prev_events, selectable=False):
        if self.corresp_start_event is None:
            if self.corresp_end_event in prev_events:
                return # we have already been rendered
            self.corresp_end_event.render(graph, layer, prev_events, selectable)
        else:
            if self.corresp_start_event in prev_events:
                return # we have already been rendered
            self.corresp_start_event.render(graph, layer, prev_events, selectable)

class IsRunningDummy(DummyEvent):
    def __init__(self, time, cpu):
        super(IsRunningDummy, self).__init__(time, Event.NO_CPU)
        self.layer = Canvas.BOTTOM_LAYER

    def render(self, graph, layer, prev_events, selectable=False):
        if self.corresp_start_event is None:
            if self.corresp_end_event in prev_events:
                return # we have already been rendered
            self.corresp_end_event.render(graph, layer, prev_events, selectable)
        else:
            if self.corresp_start_event in prev_events:
                return # we have already been rendered
            self.corresp_start_event.render(graph, layer, prev_events, selectable)

EVENT_LIST = {SuspendEvent : None, ResumeEvent : None, CompleteEvent : None,
              SwitchAwayEvent : None, SwitchToEvent : None, ReleaseEvent : None,
              DeadlineEvent : None, IsRunningDummy : None,
              InversionStartEvent : None, InversionEndEvent : None,
              InversionDummy : None, TaskDummy : None, CPUDummy : None, ActionEvent: None}

SPAN_START_EVENTS = { SwitchToEvent : IsRunningDummy, InversionStartEvent : InversionDummy }
SPAN_END_EVENTS = { SwitchAwayEvent : IsRunningDummy, InversionEndEvent : InversionDummy}
