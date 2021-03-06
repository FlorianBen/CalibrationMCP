from os import makedirs
from time import sleep
from epics import PV
import logging
import re
import csv
import queue
import time
import datetime
import smtplib
from email.utils import formatdate
from email.message import EmailMessage


class State:
    def __init__(self, ind, Vmcp, Vphos, dT) -> None:
        self.ind = ind
        self.Vmcp = Vmcp
        self.Vphos = Vphos
        self.dT = dT

    def __str__(self) -> str:
        return '[' + str(self.ind) + '] Vmcp=' + str(self.Vmcp)


class Conditionner:
    def __init__(self, P, R, filename_seq) -> None:
        self.P = P
        self.R = R
        self.filename_seq = filename_seq
        self.name = re.sub('[^a-zA-Z0-9\n\.]', '_', (P + R))
        self.out_dir = self.name + 'meas/'
        self.tol = 30
        self.dT_checking = 1.0
        self.dT_wait = 6
        self.dT_stabilization = 6
        self.init_logger()
        self.init_mailer()
        self.init_out_directory()
        try:
            self.connect_pvs()
            self.read_seq()
            self.run()
        except IOError as err:
            self.send_exception_main(err)

    def connect_pvs(self):
        self.cond_logger.info('Connection to PVs')
        self.pv_read_voltage_mcp = PV(
            '{}mod_1:ch_{}:MeasVoltage'.format(self.P, self.R))
        if self.pv_read_voltage_mcp.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:MeasVoltage'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:MeasVoltage'.format(self.P, self.R)))
        self.pv_read_current_mcp = PV(
            '{}mod_1:ch_{}:MeasCurrent'.format(self.P, self.R))
        if self.pv_read_current_mcp.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:MeasCurrent'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:MeasCurrent'.format(self.P, self.R)))
        self.pv_read_voltage_phos = PV(
            '{}mod_0:ch_{}:MeasVoltage'.format(self.P, self.R))
        if self.pv_read_voltage_phos.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:MeasVoltage'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:MeasVoltage'.format(self.P, self.R)))
        self.pv_read_current_phos = PV(
            '{}mod_0:ch_{}:MeasCurrent'.format(self.P, self.R))
        if self.pv_read_current_phos.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:MeasCurrent'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:MeasCurrent'.format(self.P, self.R)))
        self.pv_write_voltage_mcp = PV(
            '{}mod_1:ch_{}:setVoltage'.format(self.P, self.R))
        if self.pv_write_voltage_mcp.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:setVoltage'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:setVoltage'.format(self.P, self.R)))
        self.pv_write_voltage_phos = PV(
            '{}mod_0:ch_{}:setVoltage'.format(self.P, self.R))
        if self.pv_write_voltage_phos.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:setVoltage'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:setVoltage'.format(self.P, self.R)))
        self.pv_read_ramp = PV(
            '{}mod_1:ch_{}:Status:rampUp'.format(self.P, self.R))
        if self.pv_read_ramp.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:Status:rampUp'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_1:ch_{}:Status:rampUp'.format(self.P, self.R)))
        self.pv_read_ramp_phos = PV(
            '{}mod_0:ch_{}:Status:rampUp'.format(self.P, self.R))
        if self.pv_read_ramp_phos.wait_for_connection(5) == False:
            self.cond_logger.error('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:Status:rampUp'.format(self.P, self.R)))
            raise IOError('Failed to connect to PV: {}'.format(
                '{}mod_0:ch_{}:Status:rampUp'.format(self.P, self.R)))

    def init_logger(self):
        self.cond_logger = logging.getLogger(self.name + 'logger')
        self.cond_logger.setLevel(logging.INFO)
        self.handler = logging.FileHandler(self.name + '.log', 'w', 'utf-8')
        self.handler.setFormatter(logging.Formatter(
            '[%(name)s](%(levelname)s) %(asctime)s -> %(message)s T{%(thread)x}'))
        self.cond_logger.addHandler(self.handler)
        self.cond_logger.info('Logger correctly created.')

    def init_mailer(self):
        self.mail_server = smtplib.SMTP('mx.extra.cea.fr')
        self.mail_server.connect('mx.extra.cea.fr')
        self.cond_logger.info('Mailer correctly created.')

    def init_out_directory(self):
        makedirs(self.out_dir, exist_ok=True)

    def read_seq(self):
        self.cond_logger.info('Read CSV sequence.')
        self.states = queue.Queue()
        with open(self.filename_seq, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"')
            next(reader, None)  # skip the headers
            for row in reader:
                self.states.put(State(int(row[0]), float(
                    row[1])*1000, float(row[2])*1000, int(row[3])))
        self.cond_logger.info('States queue filled.')

    def run(self):
        self.cond_logger.info('Start conditionning.')
        while not self.states.empty():
            self.cond_logger.info('Ask a state.')
            state = self.states.get()
            self.cond_logger.info('Get state {}'.format(state.ind))
            self.process_state(state)
        self.set_voltage_mcp(0)
        self.set_voltage_phos(0)
        self.cond_logger.info('Conditionning done.')

    def process_state(self, state):
        self.set_voltage_mcp(state.Vmcp)
        self.set_voltage_phos(state.Vphos)
        sleep(self.dT_wait)
        self.check_ramping(state)
        self.check_state(state)
        self.measure_state(state)
        sleep(self.dT_wait)

    def check_ramping(self, state):
        self.cond_logger.info('Check ramping')
        nbtry = 10
        while self.pv_read_ramp.get() or self.pv_read_ramp_phos.get():
            self.cond_logger.warning(
                'Waiting end of ramping. Try {}'.format(nbtry))
            nbtry = nbtry-1
            if nbtry == 0:
                self.cond_logger.error('Failed to ramp!')
                raise IOError('Failed to ramp!')
            sleep(self.dT_wait)
        self.cond_logger.info(
            'Ramping done. Wait {} seconds for voltage stabilization.'.format(self.dT_stabilization))
        sleep(self.dT_stabilization)

    def check_state(self, state):
        self.cond_logger.info('Check state')
        check_pass = False
        nbtry = 10
        while not check_pass:

            vmcp = self.get_voltage_mcp()
            vmcp_ok = False
            if (state.Vmcp - self.tol < vmcp and vmcp < state.Vmcp + self.tol):
                self.cond_logger.info(
                    'Vmcp: Get = {}, Expected=[{},{}]'.format(vmcp, state.Vmcp - self.tol, state.Vmcp + self.tol, nbtry))
                vmcp_ok = True
            else:
                self.cond_logger.warning(
                    'Vmcp: Get = {}, Expected=[{},{}]. Try {}'.format(vmcp, state.Vmcp - self.tol, state.Vmcp + self.tol, nbtry))

            vphos = self.get_voltage_phos()
            vphos_ok = False
            if (state.Vphos - self.tol < vphos and vphos < state.Vphos + self.tol):
                self.cond_logger.info(
                    'Vphos: Get = {}, Expected=[{},{}]'.format(vphos, state.Vphos - self.tol, state.Vphos + self.tol))
                vphos_ok = True
            else:
                self.cond_logger.warning(
                    'Vphos: Get = {}, Expected=[{},{}]. Try {}'.format(vphos, state.Vphos - self.tol, state.Vphos + self.tol, nbtry))

            check_pass = vmcp_ok and vphos_ok

            nbtry = nbtry-1
            if nbtry == 0:
                self.cond_logger.error('Failed to put correct voltage!')
                raise IOError('Failed to put correct voltage!')
            sleep(self.dT_wait)
        self.send_mail(state)
        self.cond_logger.info(
            'Voltage corresponding to state. Ready for measurement')

    def measure_state(self, state):
        self.cond_logger.info(
            'Measure state {} for {} secondes'.format(state.ind, state.dT * 60))
        timeout = state.dT * 60

        with open(self.out_dir + 'state_' + str(state.ind).zfill(3) + '.csv', 'w', newline='') as csvfile:
            measwriter = csv.writer(csvfile, delimiter=',')
            condT = True
            timeout_start = time.time()
            while condT:
                time_meas = time.time()
                #epoch_str = datetime.datetime.fromtimestamp(time_meas).strftime('%c')
                condT = time_meas < timeout_start + timeout
                measwriter.writerow(
                    [time_meas, self.get_voltage_mcp(), self.get_voltage_phos(), self.get_current_mcp(), self.get_current_phos()])
                sleep(self.dT_checking)

        self.cond_logger.info(
            'Measurement done')

    def set_voltage_mcp(self, value):
        res = self.pv_write_voltage_mcp.put(value, wait=True)
        if res == None:
            self.cond_logger.error('Failed to put MCP voltage!')
            raise IOError('Failed to put MCP voltage!')

    def set_voltage_phos(self, value):
        res = self.pv_write_voltage_phos.put(value, wait=True)
        if res == None:
            self.cond_logger.error('Failed to put Phos voltage!')
            raise IOError('Failed to put Phos voltage!')

    def get_voltage_mcp(self):
        res = self.pv_read_voltage_mcp.get()
        if res == None:
            self.cond_logger.error('Failed to get MCP voltage!')
            raise IOError('Failed to get MCP voltage!')
        return res

    def get_voltage_phos(self):
        res = self.pv_read_voltage_phos.get()
        if res == None:
            self.cond_logger.error('Failed to get Phos voltage!')
            raise IOError('Failed to get Phos voltage!')
        return res

    def get_current_mcp(self):
        res = self.pv_read_current_mcp.get()
        if res == None:
            self.cond_logger.error('Failed to get MCP current!')
            raise IOError('Failed to get MCP current!')
        return res

    def get_current_phos(self):
        res = self.pv_read_current_phos.get()
        if res == None:
            self.cond_logger.error('Failed to get Phos current!')
            raise IOError('Failed to get Phos current!')
        return res

    def check_error_mcp(self):
        pass

    def check_error_phos(self):
        pass

    def send_mail(self, state):
        msg = EmailMessage()
        msg['Subject'] = "CONDMCP {} {}".format(self.P, self.R)
        msg['From'] = "ess-npm.mcp@cea.fr"
        msg['To'] = ['florian.benedetti@cea.fr']
        message = "State {} [Vmcp={} V | Vphos={} V] ready for measurement for {} minutes".format(
            state.ind, state.Vmcp, state.Vphos, state.dT)
        msg.set_content(message)
        try:
            self.mail_server.send_message(msg)
        except smtplib.SMTPException as e:
            self.cond_logger.error('Failed to send email {}'.format(e))
            return
        self.cond_logger.info('Mail sended succesfuly')

    def send_exception_main(self, exception):
        msg = EmailMessage()
        msg['Subject'] = 'MCPcond Exception'
        msg['From'] = "ess-npm.mcp@cea.fr"
        msg['To'] = ['florian.benedetti@cea.fr']
        msg.set_content("Exception: {}".format(exception))
        try:
            self.mail_server.send_message(msg)
        except smtplib.SMTPException as e:
            self.cond_logger.error('Failed to send email {}'.format(e))
            return
        self.cond_logger.info('Mail sended succesfuly')
