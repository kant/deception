import bge
from bge.types import *
from ..bgf import config, state, database, isKeyPressed, playSound
from ..bgf.operators import showMouseCursor
from mathutils import Vector


DEBUG = 0
TIMER_INCREMENT = 1 / 60
MOVE_SPEED_FACTOR = 2.0
MOVE_RUN_MULTIPLIER = 2.2
MOVE_CROUCH_MULTIPLIER = 0.55
MOVE_STAMINA_DRAIN = 0.00075
MOVE_STAMINA_RUN_BIAS = 0.05
MOVE_STAMINA_TIRED_BIAS = 0.4
MOUSE_LOOK_BIAS = 0.0006
INVENTORY_TOGGLE_INTERVAL = 1.4 # seconds
FLASHLIGHT_MOVE_SMOOTH = 15.0
FLASHLIGHT_MAX_ENERGY = 2.0
FLASHLIGHT_MAX_DISTANCE = 20.0
FLASHLIGHT_BATTERY_DRAIN = 0.0001 # Default: 0.0001
SOUND_STEPS_INTERVAL = 0.65 # seconds
USE_DISTANCE = 2.0 # meters
DEFAULT_PROPS = {
    "Crouch": False,
    "FlashlightClick": False,
    "Ground": "",
    "MoveH": 0,
    "MoveV": 0,
    "Run": False,
    "TimerSteps": 0.0,
    "TimerInventory": -INVENTORY_TOGGLE_INTERVAL,
    "OnInventory": False,
}


def player(cont):
    # type: (SCA_PythonController) -> None

    always = cont.sensors["Always"] # type: SCA_AlwaysSensor

    if always.positive:

        if always.status == bge.logic.KX_SENSOR_JUST_ACTIVATED:
            __init(cont)

        cont.owner["TimerInventory"] += TIMER_INCREMENT

        __inputManager(cont)
        __messageManager(cont)
        __mouseLook(cont)
        __move(cont)
        __flashlight(cont)
        __sound(cont)


def __flashlight(cont):
    # type: (SCA_PythonController) -> None

    from random import randint

    own = cont.owner
    player = state["Player"]
    flashlight = own.childrenRecursive.get("Flashlight") # type: KX_LightObject

    if flashlight:
        flashlight.timeOffset = FLASHLIGHT_MOVE_SMOOTH

        if player["FlashlightOn"]:
            flashlightForce = player["FlashlightOn"] if player["FlashlightOn"] == 2 else 0.5
            flashlightDistance = 1 if player["FlashlightOn"] == 2 else 0.01

            if player["FlashlightBattery"] > 0:
                player["FlashlightBattery"] -= FLASHLIGHT_BATTERY_DRAIN * flashlightForce

            if player["FlashlightBattery"] < 0:
                player["FlashlightBattery"] = 0.0

            if 0 < player["FlashlightBattery"] < 0.3 and randint(0, 100) < 10 or player["FlashlightBattery"] == 0:
                flashlight.energy = 0.0
            else:
                flashlight.energy = FLASHLIGHT_MAX_ENERGY * flashlightForce

            flashlight.distance = FLASHLIGHT_MAX_DISTANCE * flashlightDistance

        else:
            flashlight.energy = 0.0


def __init(cont):
    # type: (SCA_PythonController) -> None
    own = cont.owner
    own.scene.active_camera = own.childrenRecursive.get("PlayerCamera")
    own.scene["Player"] = own

    global DEBUG
    DEBUG = True if own.get("Debug") else DEBUG

    if DEBUG:
        light = own.scene.objects.get("Hemi") # type: KX_LightObject
        if light:
            light.energy = 0.5

    for key in DEFAULT_PROPS.keys():
        own[key] = DEFAULT_PROPS[key]
        if DEBUG: own.addDebugProperty(key, True)


def __inputManager(cont):
    # type: (SCA_PythonController) -> None

    own = cont.owner
    player = state["Player"]

    isUp = isKeyPressed(config["KeyUp"])
    isDown = isKeyPressed(config["KeyDown"])
    isLeft = isKeyPressed(config["KeyLeft"])
    isRight = isKeyPressed(config["KeyRight"])
    isRun = isKeyPressed(config["KeyRun"])
    isCrouch = isKeyPressed(config["KeyCrouch"])
    isFlashlight = isKeyPressed(config["KeyFlashlight"], status=1)
    isUse = isKeyPressed(config["KeyUse"], status=1)
    isInventory = isKeyPressed(config["KeyInventory"], status=1)

    # Toggle inventory
    if isInventory and own["TimerInventory"] >=0:
        own["OnInventory"] = not own["OnInventory"]
        own["TimerInventory"] = -INVENTORY_TOGGLE_INTERVAL
        camPos = "[50, 0]" if own["OnInventory"] else "[0, 0]"
        own.sendMessage("UpdateGui", camPos)

    # Turn flashlight on or off
    if isFlashlight:
        player["FlashlightOn"] = 2 if player["FlashlightOn"] == 0 else player["FlashlightOn"] - 1
        own["FlashlightClick"] = True

    if not own["OnInventory"]:

        own["Run"] = bool(isRun) if not isCrouch else False
        own["Crouch"] = bool(isCrouch) if not isRun else False

        # Use aimed object
        if isUse:
            __use(cont)

        # Vertical movement
        if isUp and not isDown:
            own["MoveV"] = 1

        elif not isUp and isDown:
            own["MoveV"] = -1

        else:
            own["MoveV"] = 0

        # Horizontal movement
        if isRight and not isLeft:
            own["MoveH"] = 1

        elif not isRight and isLeft:
            own["MoveH"] = -1

        else:
            own["MoveH"] = 0

    else:
        own["MoveH"] = 0
        own["MoveV"] = 0
        own["Run"] = False
        own["Crouch"] = False


def __messageManager(cont):
    # type: (SCA_PythonController) -> None

    own = cont.owner
    message = cont.sensors["Message"] # type: KX_NetworkMessageSensor

    if message.positive:
        for i in range(len(message.subjects)):
            subject = message.subjects[i]
            body = message.bodies[i]

            if subject == "UseItem" and body:
                inventory = state["Player"]["Inventory"] # type: list[str]
                item = database["Items"].get(body) # type: dict[str, object]

                if item and item["Usable"]:
                    inventory.remove(body)
                    playSound("ItemPickup" + str(item["Sound"]))

                    if item.get("Command"):
                        exec(item["Command"])


def __mouseLook(cont):
    # type: (SCA_PythonController) -> None

    def _mouseToCenter():
        windowSize = Vector((bge.render.getWindowWidth(), bge.render.getWindowHeight()))
        windowCenter = Vector((windowSize.x // 2, windowSize.y // 2))
        bge.render.setMousePosition(int(windowCenter.x), int(windowCenter.y))

    from math import radians, degrees

    own = cont.owner

    if own["OnInventory"]:
        showMouseCursor(cont, arg="True")

    # Enable mouse look when inventory is closed
    elif not own["OnInventory"]:
        showMouseCursor(cont, arg="False")

        if own["TimerInventory"] >= -INVENTORY_TOGGLE_INTERVAL + 0.1:
            AXIS_ANGLE_LIMIT = 89.999999
            axis = own.childrenRecursive.get("CameraAxis") # type: KX_Camera
            camRot = axis.localOrientation.to_euler()
            sensitivity = config["MouseSensitivity"] # type: float

            # Fix axis rotating beyond limit
            if degrees(camRot.x) <= -90 or degrees(camRot.x) >= 90:
                getSignal = lambda val: 1 if val >= 0 else -1
                camRot = axis.localOrientation.to_euler()
                camRot.x = radians(AXIS_ANGLE_LIMIT * getSignal(degrees(camRot.x)))
                axis.localOrientation = camRot

            windowSize = Vector((bge.render.getWindowWidth(), bge.render.getWindowHeight()))
            windowCenter = Vector((windowSize.x // 2, windowSize.y // 2))
            mousePos = Vector((bge.logic.mouse.position[0] * windowSize[0], bge.logic.mouse.position[1] * windowSize[1]))
            centerOffset = (windowCenter - mousePos) * 0.001 # type: Vector

            # Rotate player in mouse X
            if (centerOffset.x < -MOUSE_LOOK_BIAS or centerOffset.x > MOUSE_LOOK_BIAS):
                own.applyRotation((0, 0, centerOffset[0] * sensitivity))

            # Rotate axis in mouse Y
            if (centerOffset.y < -MOUSE_LOOK_BIAS or centerOffset.y > MOUSE_LOOK_BIAS):
                if -AXIS_ANGLE_LIMIT < degrees(camRot.x) < AXIS_ANGLE_LIMIT:
                    axis.applyRotation((-centerOffset.y * sensitivity, 0, 0), True)

            _mouseToCenter()

        else:
            _mouseToCenter()


def __move(cont):
    # type: (SCA_PythonController) -> None

    own = cont.owner
    player = state["Player"]

    moveFactor = MOVE_RUN_MULTIPLIER if own["Run"] and player["Stamina"] > MOVE_STAMINA_RUN_BIAS \
        else MOVE_CROUCH_MULTIPLIER if own["Crouch"] else 1.0
    moveVector = Vector([-own["MoveH"], -own["MoveV"], 0]).normalized() * MOVE_SPEED_FACTOR * moveFactor

    onGround = own.rayCast(own.worldPosition + Vector([0, 0, -1]), own, 1)

    if not onGround[0]:
        moveVector.z = own.localLinearVelocity.z
        own["Ground"] = ""

    elif "Ground" in onGround[0]:
        own["Ground"] = onGround[0]["Ground"]

    else:
        own["Ground"] = ""

    own.localLinearVelocity = moveVector

    isMoving = own["MoveH"] or own["MoveV"]

    # Drain stamina when running
    if isMoving and own["Run"] and player["Stamina"] > 0:
        player["Stamina"] -= MOVE_STAMINA_DRAIN

    # Recover stamina when walking
    elif isMoving and player["Stamina"] < 1:
        player["Stamina"] += MOVE_STAMINA_DRAIN

    # Recover stamina fast when stopped
    elif not isMoving and player["Stamina"] < 1:
        player["Stamina"] += MOVE_STAMINA_DRAIN * 2


def __sound(cont):
    # type: (SCA_PythonController) -> None

    import aud
    from random import choice, randint

    own = cont.owner
    player = state["Player"]

    own["TimerSteps"] += TIMER_INCREMENT

    # Play flashlight click sound
    if own["FlashlightClick"]:
        playSound("FlashlightClick", own)
        own["FlashlightClick"] = False

    # Panting sound when stamina is low
    if player["Stamina"] <= MOVE_STAMINA_TIRED_BIAS:
        if not "Panting" in own or own["Panting"] and own["Panting"].status == aud.AUD_STATUS_INVALID:
            handle = playSound("VoiceFemalePanting1")
            handle.volume *= 0.25
            own["Panting"] = handle

    # Play sounds when moving
    if (own["MoveH"] or own["MoveV"]):

        # Step sounds
        if own["TimerSteps"] >= 0 and own["Ground"]:
            moveFactor = 1.8 if own["Run"] and player["Stamina"] > MOVE_STAMINA_RUN_BIAS \
                else 0.65 if own["Crouch"] else 1

            own["TimerSteps"] = -SOUND_STEPS_INTERVAL / moveFactor

            soundName = "Step"
            soundName += "Run" if own["Run"] else "Walk"
            soundName += own["Ground"]
            soundName += str(choice((1, 2)))

            handle = playSound(soundName, own)
            handle.pitch = 1 + (1 / randint(8, 15) * choice((-1, 1)))
            handle.volume *= 1 if own["Run"] else 0.06 if own["Crouch"] else 0.3


def __use(cont):
    # type: (SCA_PythonController) -> None

    own = cont.owner
    camera = own.scene.active_camera

    hitObject = camera.getScreenRay(0.5, 0.5, USE_DISTANCE)

    if hitObject:

        if "Door" in hitObject:
            vect = (hitObject.parent.localPosition - own.localPosition) * hitObject.parent.localOrientation # type: Vector
            hitObject["Use"] = True

            if not hitObject["Opened"] and not hitObject.isPlayingAction():
                hitObject["Direction"] = 1 if vect.y >= 0 else 2
                hitObject["Speed"] = "Run" if own["Run"] else "Crouch" if own["Crouch"] else "Normal"

        elif "Container" in hitObject:
            hitObject["Use"] = True

