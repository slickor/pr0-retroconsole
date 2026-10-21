#!/bin/bash

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
elif [ -d "/roms/tools/PortMaster/" ]; then
  controlfolder="/roms/tools/PortMaster"
elif [ -d "/roms/ports/PortMaster/" ]; then
  controlfolder="/roms/ports/PortMaster"
elif [ -d "/ports/PortMaster/" ]; then
  controlfolder="/ports/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

if [ -f "$controlfolder/control.txt" ]; then
  source "$controlfolder/control.txt"
  [ -f "$controlfolder/tasksetter" ] && source "$controlfolder/tasksetter"
  get_controls
fi

# Robust GAMEDIR resolution (SCRIPTDIR first, then PortMaster, ArkOS, CrossMix)
SCRIPTDIR=$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)
if [ -d "$SCRIPTDIR/pr0-retroconsole" ]; then
  GAMEDIR="$SCRIPTDIR/pr0-retroconsole"
elif [ -n "$directory" ] && [ -d "/$directory/ports/pr0-retroconsole" ]; then
  GAMEDIR="/$directory/ports/pr0-retroconsole"
elif [ -d "/roms2/ports/pr0-retroconsole" ]; then
  GAMEDIR="/roms2/ports/pr0-retroconsole"
elif [ -d "/roms/ports/pr0-retroconsole" ]; then
  GAMEDIR="/roms/ports/pr0-retroconsole"
elif [ -d "/ports/pr0-retroconsole" ]; then
  GAMEDIR="/ports/pr0-retroconsole"
elif [ -d "/userdata/roms/ports/pr0-retroconsole" ]; then
  GAMEDIR="/userdata/roms/ports/pr0-retroconsole"
elif [ -d "/mnt/SDCARD/Emus/PORTS/pr0-retroconsole" ]; then
  GAMEDIR="/mnt/SDCARD/Emus/PORTS/pr0-retroconsole"
else
  GAMEDIR="$SCRIPTDIR"
fi

cd "$GAMEDIR"

# Log file for debugging on device
exec > >(tee "$GAMEDIR/log.txt") 2>&1

# Ensure uinput is writable for gamepads
if [ -n "$ESUDO" ]; then
  $ESUDO chmod 666 /dev/uinput 2>/dev/null
else
  chmod 666 /dev/uinput 2>/dev/null
fi

export PYTHONUNBUFFERED=1
export PYTHONPATH="$GAMEDIR/libs:$PYTHONPATH"

# Handheld media player and shared library search paths (TrimUI Smart Pro, CrossMix, PortMaster)
export PATH="/mnt/SDCARD/System/bin:/mnt/sdcard/System/bin:/opt/system/Tools/PortMaster/tools:/roms/ports/PortMaster/tools:$PATH"
export LD_LIBRARY_PATH="/lib:/lib64:/usr/lib:/mnt/SDCARD/System/lib:/mnt/sdcard/System/lib:/mnt/SDCARD/Apps/PortMaster/PortMaster:/mnt/sdcard/Apps/PortMaster/PortMaster:$LD_LIBRARY_PATH"

# Verify essential dependencies (pygame and pure-python requests)
if ! PYTHONPATH="$GAMEDIR/libs:$PYTHONPATH" python3 -c "import pygame, requests" >/dev/null 2>&1; then
  echo "Dependencies missing, running installer..."
  bash ./install.sh
fi

if ! PYTHONPATH="$GAMEDIR/libs:$PYTHONPATH" python3 -c "import pygame" >/dev/null 2>&1; then
  echo "Pygame could not be loaded. Please run: sudo apt-get install python3-pygame"
  exit 1
fi

# Launch gptokeyb daemon for handheld button-to-key translation
if [ -n "$GPTOKEYB" ] && [ -f "$controlfolder/gptokeyb" ]; then
  export GPTOKEYB_ACTIVE=1
  $GPTOKEYB "python3" -c "./pr0.gptk" &
fi

export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"

echo "Starting pr0-retroconsole..."
python3 src/main.py --config config.json

# Cleanup gptokeyb on exit
if [ -f "$controlfolder/gptokeyb" ]; then
  if [ -n "$ESUDO" ]; then
    $ESUDO kill -9 $(pidof gptokeyb) 2>/dev/null
    $ESUDO systemctl restart oga_events & 2>/dev/null
  else
    kill -9 $(pidof gptokeyb) 2>/dev/null
  fi
fi

echo "pr0-retroconsole closed."
