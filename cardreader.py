"""
!!!
WARNING:  this code may have bugs!! It has not been tested in its intended
environment for long at all. If you find any issues, please raise them on the
GitHub page linked below, or email uCreate.
!!!

Run this code on a Raspberry Pi. With a USB MIFARE card reader acting as a
virtual keyboard plugged in, this program will write out the data read from the
scanned card, along with the current date and time, to monthly files in
LOCAL_OUTPUT_DIR.

If a USB stick is plugged in to the RPi, when the pushbutton is pressed, this
program will mount the USB stick (currently hardcoded to be /dev/sda) to
USB_MOUNT_DIR, write out any new or updated cardinfo files from LOCAL_OUTPUT_DIR,
and unmount the USB stick when finished.

Green and red LEDs show ready and busy status respectively.
Buzzer will make an unhappy signal upon any errors mounting, writing to, or
unmounting the USB stick.

Code is maintained at github.com/eduCreateStudio/cardreader.pi
For annoying eduroam/SSL/DHCP/DNS reasons, git cannot clone repos on the RPi
at the moment. You will have to manually update this code from the remote repo.
 

TODO:
    make global constant names consistent in format
    add global constants for datetime format strings
    ...

"""


import logging
import sys, fcntl, os
import subprocess
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime

LOCAL_OUTPUT_DIR = 'files/'
USB_MOUNT_DIR = '/media/usb/'

global filename

## CHANGE ME DEPENDING ON THE ROOM I AM TO BE INSTALLED IN ##
## e.g. 1.11, workshop, KBmakerspace, etc. ...
room_id = "ROOM-ID"


def lock_file(f):
    if f.writable(): fcntl.lockf(f, fcntl.LOCK_EX)

def unlock_file(f):
    if f.writable(): fcntl.lockf(f, fcntl.LOCK_UN)

# thomas lux (so/a/46407326)
class AtomicOpen:
    # open file, acquire lock
    def __init__(self, path, *args, **kwargs):
        self.file = open(path, *args, **kwargs)
        lock_file(self.file)

    # return opened file
    def __enter__(self, *args, **kwargs):
        return self.file

    # unlock and close file
    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        self.file.flush()
        os.fsync(self.file.fileno())
        unlock_file(self.file)
        self.file.close()
        if (exc_type != None):
            return False
        else:
            return True

# unhappy buzzer signal
def buzzer_signal_bad():
    buzzer.ChangeFrequency(98)
    buzzer.start(50)
    sleep(0.08)
    buzzer.stop()
    sleep(0.08)
    buzzer.ChangeFrequency(98)
    buzzer.start(50)
    sleep(0.2)
    buzzer.stop()

# main loop - wait for card, write card number out to file
def card_loop():
    while (1):
        # blocking wait on input()
        snumber = input()
        # indicate busy with red LED
        GPIO.output(greenLED, 0)
        GPIO.output(redLED, 1)

        # check that local files dir exists - create it if not
        if not os.path.isdir(LOCAL_OUTPUT_DIR):
            logging.info(" {LOCAL_OUTPUT_DIR} dir does not exist. creating now..")
            os.mkdir(LOCAL_OUTPUT_DIR)

        # make filename for this room, month, and day
        filename = LOCAL_OUTPUT_DIR + "cardinfo_" + room_id + "_" + datetime.now().strftime('%b-%Y')
        # write card number to file
        with AtomicOpen(filename, mode='a') as cardnumfile:
            current_datetime = datetime.now().strftime('%Y-%m-%dT%H:%M:%S') 
            cardnumfile.write(snumber + "," + current_datetime  + '\n') 
            logging.info(f" wrote out {snumber} to {filename}")
            logging.debug(f" wrote out {snumber}, {current_datetime} to {filename}")
        # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1)        

def button_callback(channel):
    logging.info(" button pressed!")
    # indicate busy with red LED
    GPIO.output(greenLED, 0)
    GPIO.output(redLED, 1)
    # copy over files to USB
    # mount USB (should be sda1) to media/usb. TODO: fallback to sdb, sdc...
    try:
        subprocess.run(['sudo','mount','-o','uid=1000,gid=1000','/dev/sda1', USB_MOUNT_DIR], check=True)
    except subprocess.CalledProcessError as exc:
        logging.error(f" USB drive mount failed with error code {exc.returncode}")
        buzzer_signal_bad()
        # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1)
        return
    logging.info(f" successfully mounted USB drive to {USB_MOUNT_DIR}")

    #scan existing card number files in this file dir
    try: 
        ls_output = subprocess.check_output(['ls', LOCAL_OUTPUT_DIR])
    except subprocess.CalledProcessError as exc:
        logging.info(f" ls failed with error code {exc.returncode}")
        buzzer_signal_bad()
        # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1)
        return
    local_existing_cardnumfiles = list(filter(lambda s: s.startswith("cardinfo_"), ls_output.decode().split('\n')))
    # print(f"[DEBUG] {local_existing_cardnumfiles}")
    
    # scan files in usb root dir
    try:
        ls_output = subprocess.check_output(['ls', USB_MOUNT_DIR])
    except subprocess.CalledProcessError as exc:
        logging.error(f" ls failed with error code {exc.returncode}")
        buzzer_signal_bad()
        # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1)
        return
    usb_existing_cardnumfiles = list(filter(lambda s: s.startswith("cardinfo_"), ls_output.decode().split('\n')))
    # print(f"[DEBUG] {usb_existing_cardnumfiles}")

    # copy over new files to usb
            # if file already exists on usb but there is a change to md5sum from local one, then copy it over too
            # this covers cases where a file is copied over too early, and more data is written locally after
    for lf in local_existing_cardnumfiles:
        if lf in usb_existing_cardnumfiles:
            # get md5sum of both
            try:
                local_md5sum = subprocess.check_output(['md5sum', LOCAL_OUTPUT_DIR+lf])
            except subprocess.CalledProcessError as exc:
                logging.error(f" local md5sum failed with error code {exc.returncode}")
                buzzer_signal_bad()
                # indicate ready with green LED
                GPIO.output(redLED, 0)
                GPIO.output(greenLED, 1)
                return
            try:
                usb_md5sum = subprocess.check_output(['md5sum',  USB_MOUNT_DIR+lf])
            except subprocess.CalledProcessError as exc:
                logging.error(f" usb md5sum failed with error code {exc.returncode}")
                buzzer_signal_bad()
                # indicate ready with green LED
                GPIO.output(redLED, 0)
                GPIO.output(greenLED, 1) 
                return
            # if differ, copy over file
            # TODO: check that file is not locked!
                # not having this check is not a huge problem, but it would be nice to have...
                # tried with fcntl, but behaviour is not as expected.
            if not local_md5sum==usb_md5sum:
                try:
                    subprocess.run(['sudo','cp', LOCAL_OUTPUT_DIR+lf, USB_MOUNT_DIR+lf], check=True)
                except subprocess.CalledProcessError as exc:
                    logging.error(f" cp failed with error code {exc.returncode}")
                    buzzer_signal_bad()
                    # indicate ready with green LED
                    GPIO.output(redLED, 0)
                    GPIO.output(greenLED, 1) 
                    return
                
                # WE ALSO NEED TO ADD DATE TAKEN!
                try:
                    subprocess.run(['sudo','mv', USB_MOUNT_DIR+lf, USB_MOUNT_DIR+lf+"__TAKEN"+datetime.now().strftime('%d-%b-%Y')], check=True)
                except subprocess.CalledProcessError as exc:
                    logging.error(f" mv failed with error code {exc.returncode}")
                    buzzer_signal_bad()
                    # indicate ready with green LED
                    GPIO.output(redLED, 0)
                    GPIO.output(greenLED, 1)
                    return

                logging.info(f" successfully copied over {lf} to usb drive, and renamed it to {lf}"+"__TAKEN"+datetime.now().strftime('%d-%b-%Y') )

        else:
            # not on usb yet, so copy over file
            try:
                subprocess.run(['sudo','cp', LOCAL_OUTPUT_DIR+lf, USB_MOUNT_DIR+lf], check=True)
            except subprocess.CalledProcessError as exc:
                logging.error(f" cp failed with error code {exc.returncode}")
                buzzer_signal_bad()
                # indicate ready with green LED
                GPIO.output(redLED, 0)
                GPIO.output(greenLED, 1) 
                return
            
            # WE ALSO NEED TO ADD DATE TAKEN!
            try:
                subprocess.run(['sudo','mv', USB_MOUNT_DIR+lf, USB_MOUNT_DIR+lf+"__TAKEN"+datetime.now().strftime('%d-%b-%Y')], check=True)
            except subprocess.CalledProcessError as exc:
                logging.error(f" mv failed with error code {exc.returncode}")
                buzzer_signal_bad()
                # indicate ready with green LED
                GPIO.output(redLED, 0)
                GPIO.output(greenLED, 1)
                return

            logging.info(f" successfully copied over {lf} to usb drive, and renamed it to {lf}"+"__TAKEN"+datetime.now().strftime('%d-%b-%Y') )


    
    # unmount usb
    try:
        subprocess.run(['sudo','umount', USB_MOUNT_DIR])
    except subprocess.CalledProcessError as exc:
        logging.error(f" umount failed with error code {exc.returncode}")
        buzzer_signal_bad()
        # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1) 
        return
    logging.info(f" successfully unmounted USB drive")

    # indicate ready with green LED
    GPIO.output(redLED, 0)
    GPIO.output(greenLED, 1)


logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

GPIO.setmode(GPIO.BOARD)

greenLED = 31
redLED = 29
buzzerpin = 32
buttonpin = 11

output_chanlist = [greenLED,redLED,buzzerpin]

GPIO.setup(output_chanlist, GPIO.OUT)
GPIO.setup(buttonpin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

buzzer = GPIO.PWM(buzzerpin, 98)

GPIO.output(redLED, 0)
GPIO.output(greenLED, 1)

try:
    GPIO.add_event_detect(buttonpin, GPIO.RISING, callback=button_callback)
    card_loop()
except KeyboardInterrupt:
    GPIO.cleanup()
    sys.exit()

