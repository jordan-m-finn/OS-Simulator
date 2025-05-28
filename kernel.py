### Fill in the following information before submitting
# Group id: 26
# Members: Jordan Finn, Mohammad Mirzaei, Maitreyi Sinha


from collections import deque

# PID is just an integer, but it is used to make it clear when a integer is expected to be a valid PID.
PID = int

# This class represents the PCB of processes.
# It is only here for your convinience and can be modified however you see fit.
class PCB:
    pid: PID

    def __init__(self, pid: PID, priority=float('inf'), process_type="Foreground"):
        self.pid = pid
        self.priority = priority
        # Add a field to track if the process is blocked by a mutex or semaphore
        self.blocked_by = None  # Will store the ID of the mutex/semaphore blocking this process
        self.blocked_type = None  # Will store 'mutex' or 'semaphore'
        self.process_type = process_type
        self.remaining_quantum = 40 if process_type == "Foreground" else None

# This class represents the Kernel of the simulation.
# The simulator will create an instance of this object and use it to respond to syscalls and interrupts.
# DO NOT modify the name of this class or remove it.
class Kernel:
    scheduling_algorithm: str
    ready_queue: deque[PCB]
    waiting_queue: deque[PCB]
    running: PCB
    idle_pcb: PCB

    # Called before the simulation begins.
    # Use this method to initilize any variables you need throughout the simulation.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def __init__(self, scheduling_algorithm: str, logger):
        self.scheduling_algorithm = scheduling_algorithm
        self.ready_queue = deque()
        self.waiting_queue = deque()
        self.idle_pcb = PCB(0)
        self.running = self.idle_pcb
        self.logger = logger
        
        # Initialize data structures for mutexes and semaphores
        self.mutexes = {}  # Dictionary to store mutex information: {mutex_id: {'locked': bool, 'owner': PID, 'waiting': deque}}
        self.semaphores = {}  # Dictionary to store semaphore information: {semaphore_id: {'value': int, 'waiting': deque}}
        
        # For Round Robin scheduling
        self.time_quantum = 40  # 40 microseconds time quantum
        self.current_time = 0  # Track current time for RR scheduling
        self.process_start_time = 0  # Track when the current process started running

        #multi-level scheduling
        self.foreground_queue = deque() #RR
        self.background_queue = deque() #FCFS
        self.current_level= None
        self.level_timer = 0

        self.pcbs= {}

    # This method is triggered every time a new process has arrived.
    # new_process is this process's PID.
    # priority is the priority of new_process.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    #process_type is either foreground or background
    def new_process_arrived(self, new_process: PID, priority: int, process_type: str) -> PID:
        pcb = PCB(new_process, priority=priority, process_type=process_type)
        self.pcbs[new_process] = pcb
        if self.scheduling_algorithm=="Multilevel":
            if process_type == "Foreground":
                #uses RR scheduling algorithm
                if self.running is self.idle_pcb:
                    if self.current_level != process_type:
                        self.level_timer = 0
                    self.running = pcb
                    self.current_level = process_type
                    self.process_start_time = self.current_time
                    return pcb.pid
                else:
                    self.foreground_queue.append(pcb)
                    print("Self.running.pid is returned: ", self.running.pid)
                    return self.running.pid
            else:
                if self.running is self.idle_pcb:
                    if self.current_level != process_type:
                        self.level_timer = 0
                    self.running = pcb
                    self.process_start_time = self.current_time
                    self.current_level = process_type
                    return pcb.pid
                else:
                    self.background_queue.append(pcb)
                    return self.running.pid
                
        if self.scheduling_algorithm == "Priority":
            if self.running.priority <= priority:
                self.ready_queue.append(pcb)
            else:
                #preempt current process and start executing the higher priority process (smaller priority number)
                self.ready_queue.append(self.running)
                self.running = pcb
                
        elif self.scheduling_algorithm == "FCFS":
            #If the currently running process is not the idle process, let the currently running process keep running
            #and add the new_process to the ready queue. 
            if self.running is not self.idle_pcb:
                self.ready_queue.append(pcb)
            #Otherwise, set the running process to the new_process.
            else:
                self.running = pcb
        
        elif self.scheduling_algorithm == "RR":
            # For Round Robin, if no process is running (idle), run the new process
            if self.running is self.idle_pcb:
                self.running = pcb
                self.process_start_time = self.current_time
            else:
                # Otherwise, add the new process to the ready queue
                self.ready_queue.append(pcb)

        return self.running.pid

    # This method is triggered every time the current process performs an exit syscall.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_exit(self) -> PID:
        exited = self.running
        self.running = self.idle_pcb

        # Clean up: remove exited process from any queues just in case
        if exited in self.foreground_queue:
            self.foreground_queue.remove(exited)
        if exited in self.background_queue:
            self.background_queue.remove(exited)
        if exited in self.ready_queue:
            self.ready_queue.remove(exited)

        # Clean up: remove all semaphore and mutex waiting queues
        for sem in self.semaphores.values():
            if exited in sem['waiting']:
                sem['waiting'].remove(exited)
        for mutex in self.mutexes.values():
            if exited in mutex['waiting']:
                mutex['waiting'].remove(exited)

        self.running = self.choose_next_process()
        if self.scheduling_algorithm == "RR" or self.scheduling_algorithm == "Multilevel":
            self.process_start_time = self.current_time


        return self.running.pid

    # This method is triggered when the currently running process requests to change its priority.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_set_priority(self, new_priority: int) -> PID:
        self.running.priority = new_priority
        if self.scheduling_algorithm == "Priority":
            if self.ready_queue and any(process.priority < self.running.priority for process in self.ready_queue):
                self.ready_queue.append(self.running)
                self.ready_queue = deque(sorted(self.ready_queue, key=lambda x: x.priority))
                self.running = self.ready_queue.popleft()
        return self.running.pid


    # This is where you can select the next process to run.
    # This method is not directly called by the simulator and is purely for your convinience.
    # Feel free to modify this method as you see fit.
    # It is not required to actually use this method but it is recommended.
    def choose_next_process(self):
        if self.scheduling_algorithm == "Multilevel":
            if self.current_level == "Foreground":
                if len(self.foreground_queue) > 0:
                    return self.foreground_queue.popleft()
                elif len(self.background_queue) >0:
                    self.current_level = "Background"
                    self.level_timer = 0
                    return self.background_queue.popleft()
            else:  # current_level == "Background"
                if len(self.background_queue) > 0:
                    #print("Choosing background process now: ", self.background_queue)
                    return self.background_queue.popleft()
                elif len(self.foreground_queue) > 0:
                    self.current_level = "Foreground"
                    self.level_timer = 0
                    return self.foreground_queue.popleft()
        elif self.scheduling_algorithm == "FCFS" and self.ready_queue:
            return self.ready_queue.popleft()
        elif self.scheduling_algorithm == "Priority" and self.ready_queue:
            self.ready_queue = deque(sorted(self.ready_queue, key=lambda x: x.priority))
            return self.ready_queue.popleft()
        elif self.scheduling_algorithm == "RR" and self.ready_queue:
            # For Round Robin, simply take the next process from the ready queue
            return self.ready_queue.popleft()

        return self.ready_queue.popleft() if self.ready_queue else self.idle_pcb
    
    # The following are new methods that the simulator will call for the new simulations (i.e. for project 1). 
    # You will notice that some of them do not return a PID and thus can not cause a context switch.

    # This method is triggered when the currently running process requests to initialize a new semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_semaphore(self, semaphore_id: int, initial_value: int):
        # Initialize a new semaphore with the given ID and initial value
        self.semaphores[semaphore_id] = {
            'value': initial_value,
            'waiting': deque()  # Queue of processes waiting on this semaphore
        }
        return
    
    # This method is triggered when the currently running process calls p() on an existing semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_p(self, semaphore_id: int) -> PID:
        self.semaphores[semaphore_id]['value'] -= 1

        if self.semaphores[semaphore_id]['value'] < 0:
            # Block current process
            blocked_process = self.running
            blocked_process.blocked_by = semaphore_id
            blocked_process.blocked_type = 'semaphore'
            self.semaphores[semaphore_id]['waiting'].append(blocked_process)

            # Perform context switch
            self.running = self.choose_next_process()

            # If no ready process, switch to idle
            if self.running == blocked_process:
                self.running = self.idle_pcb

            if self.scheduling_algorithm == "RR":
                self.process_start_time = self.current_time

        return self.running.pid

    # This method is triggered when the currently running process calls v() on an existing semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_v(self, semaphore_id: int) -> PID:
        # Increment the semaphore value
        self.semaphores[semaphore_id]['value'] += 1
        # If there are processes waiting on this semaphore, unblock one
        if self.semaphores[semaphore_id]['value'] <= 0 and self.semaphores[semaphore_id]['waiting']:
            # Select the appropriate process to unblock based on the scheduling algorithm
            if self.scheduling_algorithm == "Priority":
                waiting_queue = sorted(self.semaphores[semaphore_id]['waiting'], key=lambda x: x.priority)
            else:  # FCFS or RR
                waiting_queue = sorted(self.semaphores[semaphore_id]['waiting'], key=lambda x: x.pid)

            process_to_release = waiting_queue[0]

            # Remove the process from the semaphore's waiting queue
            self.semaphores[semaphore_id]['waiting'].remove(process_to_release)

            # Clear the blocked status
            process_to_release.blocked_by = None
            process_to_release.blocked_type = None

            if process_to_release not in self.ready_queue:
                self.ready_queue.append(process_to_release)

            # Preempt current running process if Priority scheduling and needed
            if self.scheduling_algorithm == "Priority":
                if self.running != self.idle_pcb and self.running.priority > process_to_release.priority:
                    self.ready_queue.append(self.running)
                    self.running = self.choose_next_process()

        return self.running.pid

    # This method is triggered when the currently running process requests to initialize a new mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_mutex(self, mutex_id: int):
        # Initialize a new mutex with the given ID
        self.mutexes[mutex_id] = {
            'locked': False,
            'owner': None,
            'waiting': deque()  # Queue of processes waiting on this mutex
        }
        return

    # This method is triggered when the currently running process calls lock() on an existing mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_lock(self, mutex_id: int) -> PID:
        # If the mutex is not locked, lock it and set the owner
        if not self.mutexes[mutex_id]['locked']:
            self.mutexes[mutex_id]['locked'] = True
            self.mutexes[mutex_id]['owner'] = self.running.pid
        else:
            # If the mutex is already locked, block the process
            current_process = self.running
            current_process.blocked_by = mutex_id
            current_process.blocked_type = 'mutex'
            
            # Add the process to the mutex's waiting queue
            self.mutexes[mutex_id]['waiting'].append(current_process)
            
            # Choose the next process to run
            self.running = self.choose_next_process()
            if self.scheduling_algorithm == "RR":
                self.process_start_time = self.current_time
        
        return self.running.pid

    # This method is triggered when the currently running process calls unlock() on an existing mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_unlock(self, mutex_id: int) -> PID:
        # Only the owner can unlock the mutex
        if self.mutexes[mutex_id]['owner'] == self.running.pid:
            # If there are processes waiting on this mutex, unblock one
            if self.mutexes[mutex_id]['waiting']:
                if self.scheduling_algorithm == "Priority":
                    waiting_queue = sorted(self.mutexes[mutex_id]['waiting'], key=lambda x: x.priority)
                else:  # FCFS or RR
                    waiting_queue = sorted(self.mutexes[mutex_id]['waiting'], key=lambda x: x.pid)

                process_to_release = waiting_queue[0]

                # Remove the process from the mutex's waiting queue
                self.mutexes[mutex_id]['waiting'].remove(process_to_release)

                # Clear the blocked status
                process_to_release.blocked_by = None
                process_to_release.blocked_type = None

                # set the new owner of the mutex
                self.mutexes[mutex_id]['owner'] = process_to_release.pid

                if process_to_release not in self.ready_queue:
                    self.ready_queue.append(process_to_release)

                # Preempt if priority is higher
                if self.scheduling_algorithm == "Priority":
                    if self.running != self.idle_pcb and self.running.priority > process_to_release.priority:
                        self.ready_queue.append(self.running)
                        self.running = self.choose_next_process()
            else:
                # If no processes are waiting, unlock the mutex
                self.mutexes[mutex_id]['locked'] = False
                self.mutexes[mutex_id]['owner'] = None
                
        return self.running.pid

    # This function represents the hardware timer interrupt.
    # It is triggered every 10 microseconds and is the only way a kernel can track passing time.
    # Do not use real time to track how much time has passed as time is simulated.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def timer_interrupt(self) -> PID:
        # Update the current time
        self.current_time += 10  # Timer interrupt occurs every 10 microseconds
        #self.logger.log("Timer interrupt")
        # For Round Robin scheduling, check if the current process has used its time quantum
        if self.scheduling_algorithm == "RR" and self.running is not self.idle_pcb:
            time_used = self.current_time - self.process_start_time
            
            # If the process has used its time quantum, preempt it
            if time_used >= self.time_quantum:
                # Add the current process to the ready queue
                self.ready_queue.append(self.running)
                
                # Choose the next process to run
                self.running = self.choose_next_process()
                
                # Reset the process start time
                self.process_start_time = self.current_time
        if self.scheduling_algorithm == "Multilevel":
            if self.running.process_type == "Foreground":
                self.running.remaining_quantum -=10
            time_used = self.current_time - self.process_start_time
            self.level_timer += 10
            # 1. Handle level switching
            if self.level_timer >= 200:
                #self.logger.log("200ms has passed -- timer interrupt, switch levels")
                if self.current_level == "Foreground" and len(self.background_queue) > 0:
                    if self.running is not self.idle_pcb:
                        #self.logger.log(f"Remainig quantum for current fg process: {self.running.pid} and time left: {self.running.remaining_quantum}")
                        if self.running.remaining_quantum > 0:
                            self.foreground_queue.appendleft(self.running)
                        else:
                            self.running.remaining_quantum = 40 #reset quantum
                            self.foreground_queue.append(self.running)
                    self.current_level = "Background"
                    self.running = self.choose_next_process() 
                    self.process_start_time = self.current_time

                elif self.current_level == "Background" and len(self.foreground_queue) > 0:   
                    if self.running is not self.idle_pcb:
                        #self.logger.log(f"Preempting background process: f{self.running.pid} time slot: {self.level_timer}")
                        self.background_queue.appendleft(self.running)
                    self.current_level = "Foreground"
                    self.running = self.choose_next_process()
                    self.process_start_time = self.current_time
                    time_used = 0

                self.level_timer = 0  # recommit to current level

            # 2. Handle RR preemption inside foreground
            if self.current_level == "Foreground" and self.running.remaining_quantum <= 0 and self.running.process_type == "Foreground" :
                #self.logger.log(f"Preempting current process: {self.running.pid}  time_used: {time_used} level time: {self.level_timer}")
                self.running.remaining_quantum = 40  
                self.foreground_queue.append(self.running)
                self.running = self.choose_next_process()
                self.process_start_time = self.current_time
        return self.running.pid
