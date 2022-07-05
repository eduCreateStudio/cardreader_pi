import sys, fcntl, os
import subprocess
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime

LOCAL_OUTPUT_DIR = 'files/'
USB_MOUNT_DIR = '/media/usb/'

global filename

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
            print(f"[INFO] {LOCAL_OUTPUT_DIR} dir does not exist. creating now..")
            os.mkdir(LOCAL_OUTPUT_DIR)

        # make filename for this month
        filename = LOCAL_OUTPUT_DIR+"cardnumbers_" + datetime.now().strftime('%b') + "_" + str(datetime.now().year) 
        # write card number to file
        with AtomicOpen(filename, mode='a') as cardnumfile:
            cardnumfile.write(snumber + '\n') 
            print(f"[INFO] wrote out {snumber} to {filename}")
            # indicate ready with green LED
        GPIO.output(redLED, 0)
        GPIO.output(greenLED, 1)
        sleep(1)        

def button_callback(channel):
    print(f"[INFO] button pressed!")
    # indicate busy with red LED
    GPIO.output(greenLED, 0)
    GPIO.output(redLED, 1)
    # copy over files to USB
    # mount USB (should be sda1) to media/usb. TODO: fallback to sdb, sdc...
    try:
        subprocess.run(['sudo','mount','-o','uid=1000,gid=1000','/dev/sda1', USB_MOUNT_DIR])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] USB drive mount failed with error code {mount_rtn}")
        buzzer_signal_bad()
        return
    print(f"[INFO] successfully mounted USB drive to {USB_MOUNT_DIR}")

    #scan existing card number files in this file dir
    try: 
        ls_output = subprocess.check_output(['ls', LOCAL_OUTPUT_DIR])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] ls failed with error code {exc.returncode}")
        buzzer_signal_bad()
        return
    local_existing_cardnumfiles = list(filter(lambda s: s.startswith("cardnumbers"), ls_output.decode().split('\n')))
    # print(f"[DEBUG] {local_existing_cardnumfiles}")
    
    # scan files in usb root dir
    try:
        ls_output = subprocess.check_output(['ls', USB_MOUNT_DIR])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] ls failed with error code {exc.returncode}")
        buzzer_signal_bad()
        return
    usb_existing_cardnumfiles = list(filter(lambda s: s.startswith("cardnumbers"), ls_output.decode().split('\n')))
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
                print(f"[ERROR] local md5sum failed with error code {exc.returncode}")
                buzzer_signal_bad()
                return
            try:
                usb_md5sum = subprocess.check_output(['md5sum',  USB_MOUNT_DIR+lf])
            except subprocess.CalledProcessError as exc:
                print(f"[ERROR] usb md5sum failed with error code {exc.returncode}")
                buzzer_signal_bad()
                return
            # if differ, copy over file
            # TODO: check that file is not locked!
                # not having this check is not a huge problem, but it would be nice to have...
            if not local_md5sum==usb_md5sum:
                try:
                    subprocess.run(['sudo','cp', LOCAL_OUTPUT_DIR+lf, USB_MOUNT_DIR+lf])
                except subprocess.CalledProcessError as exc:
                    print(f"[ERROR] cp failed with error code {exc.returncode}")
                    buzzer_signal_bad()
                    return
                print(f"[INFO] successfully copied over {lf} to usb drive")
        else:
            # not on usb yet, so copy over file
            try:
                subprocess.run(['sudo','cp', LOCAL_OUTPUT_DIR+lf, USB_MOUNT_DIR+lf])
            except subprocess.CalledProcessError as exc:
                print(f"[ERROR] cp failed with error code {exc.returncode}")
                buzzer_signal_bad()
                return
            print(f"[INFO] successfully copied over {lf} to usb drive")
    
    # unmount usb
    try:
        subprocess.run(['sudo','umount', USB_MOUNT_DIR])
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] umount failed with error code {exc.returncode}")
        buzzer_signal_bad()
        return
    print(f"[INFO] successfully unmounted USB drive")

    # indicate ready with green LED
    GPIO.output(redLED, 0)
    GPIO.output(greenLED, 1)



GPIO.setmode(GPIO.BOARD)

greenLED = 31
redLED = 29
buzzerpin = 32
buttonpin = 11

output_chanlist = [greenLED,redLED,buzzerpin]

GPIO.setup(output_chanlist, GPIO.OUT)
GPIO.setup(buttonpin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

buzzer = GPIO.PWM(buzzerpin, 98)

try:
    GPIO.add_event_detect(buttonpin, GPIO.RISING, callback=button_callback)
    card_loop()
except KeyboardInterrupt:
    GPIO.cleanup()
    sys.exit()

