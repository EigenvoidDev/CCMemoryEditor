# CCMemoryEditor

[Castle Crashers](https://www.castlecrashers.com/) is a beat 'em up video game developed and published by [The Behemoth](https://www.thebehemoth.com/).

**CCMemoryEditor** is a desktop GUI tool for Castle Crashers that allows you to view and modify in-game character data directly from memory. It provides real-time scanning of the game process, lets you edit stats and unlocks for individual characters, and offers a straightforward interface for applying changes instantly.

## Installation

### Option 1: Run from Source

If you are running the application from source (e.g., cloned from GitHub), make sure you have [Python 3.9 or higher](https://www.python.org/downloads/) installed, and install both [Pymem](https://pypi.org/project/Pymem/) and [PyQt6](https://pypi.org/project/PyQt6/) using pip:
```
pip install Pymem PyQt6
```
Next, open a terminal, navigate to the application's root directory, and run:
```
python main.py
```

### Option 2: Prebuilt Executable

If you are on **Windows**, download the prebuilt executable from the [Releases page](https://github.com/EigenvoidDev/CCMemoryEditor/releases). Once downloaded, simply double-click the file to launch the application.

#### Windows Security Warnings

On **Windows 8 and newer**, you may see a **SmartScreen warning** because this application is unsigned. The application is not digitally signed because code-signing certificates require a paid license. As a result, Windows may label it as being from an unknown publisher.

Similarly, some antivirus software may flag the application as suspicious or prevent it from being downloaded. These detections are **false positives**. 

You can verify the safety of the application by reviewing the source code directly in this repository or building the executable yourself.

If your antivirus software blocks the application, consider adding it to your allowlist or exclusions.

## Usage
1. Launch Castle Crashers and load to the title screen.
2. Open CCMemoryEditor. The tool will automatically detect the game process and populate the editor with character data. Wait until the data is loaded before interacting.
3. Select a character from the list. You can then edit stats and unlocks for that character.
4. Click the "Apply Changes" button to update the character data in memory instantly.
5. To save your changes, load the selected character into a level and then select "Exit To Map".

## Important Notes

### Launch Castle Crashers First
To ensure that the tool can detect and scan the game process correctly, launch `castle.exe` *before* opening CCMemoryEditor. The integrated scan delay helps even if you open the tool before launching the game, but launching the game first is recommended for smooth operation.

### Fast Scan Enabled by Default in Prebuilt Executable
The prebuilt executable sets **Fast Scan** to true by default. Fast Scan optimizes memory scanning by skipping certain memory ranges and starting at address `0x07000000`. Character data in Castle Crashers consistently resides in heap-allocated regions starting above this address, so restricting the scan improves performance and avoids noise. You can toggle this behavior by changing the `FAST_SCAN` variable in `config.py`. Setting it to `False` will scan the entire process memory instead.

### DLC Unlocks are not Permanent
Any changes you make to unlock DLC are temporary. The game verifies DLC ownership each time it launches, so any DLC-dependent items or features will be removed when restarting the game.

### Stats Limits
The game enforces maximum values for stats (e.g., 99 for Level; 25 for Strength, Defense, Magic, and Agility). If you exceed these values, your changes may be rolled back when the game closes. You can always reapply your desired configuration within these limits.

## License

CCMemoryEditor is licensed under the [GNU General Public License v3.0 (GPLv3)](https://github.com/EigenvoidDev/CCMemoryEditor/blob/main/LICENSE).