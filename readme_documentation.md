# System Audio FFT for Blender

Real-time audio analysis addon that captures system audio output and provides FFT data for audio-reactive animations in Blender.

![Addon Demo](demo.gif) <!-- You'll need to create this -->

## Features

- **System Audio Capture**: Captures audio output from any application (VITAL, VLC, Spotify, games, etc.)
- **Real-time FFT Analysis**: 16 frequency bins with logarithmic spacing optimized for music
- **Custom Node**: Intuitive dropdown selection for frequency ranges (Sub Bass, Bass, Mid, etc.)
- **Live Preview**: Real-time visualization of FFT values in the UI
- **Cross-Platform**: Works on Linux (PulseAudio/PipeWire), Windows (WASAPI), and macOS (with additional setup)
- **Easy Integration**: Direct scene properties and manual driver setup for animations

## Installation

### Prerequisites

Install required Python libraries in Blender's Python environment:

```bash
# Linux/macOS
/path/to/blender/python/bin/pip install numpy pyaudio

# Windows (run as administrator in Blender's Python folder)
python -m pip install numpy pyaudio
```

### Install Addon

1. Download the latest `blender_audio_fft_fixed.py` from releases
2. In Blender: Edit → Preferences → Add-ons → Install
3. Select the downloaded .py file
4. Enable "System Audio FFT - User Friendly"

## System Audio Setup

### Linux (PulseAudio/PipeWire)
1. Install `pavucontrol`: `sudo apt install pavucontrol`
2. Start the addon and begin audio capture
3. Open `pavucontrol` → Recording tab
4. Find Blender process and change input from microphone to "Monitor of [your audio device]"

### Windows
1. Right-click sound icon → Recording devices
2. Enable "Stereo Mix" if available
3. Or install [VB-Audio Cable](https://vb-audio.com/Cable/) for virtual audio routing

### macOS
1. Install [BlackHole](https://existential.audio/blackhole/) or [Soundflower](https://github.com/mattingalls/Soundflower)
2. Set up audio routing through the virtual device

## Usage

### Quick Start
1. Open Node Editor → Sidebar → Audio FFT tab
2. Click "▶ Start" to begin audio capture
3. Play audio in any application (VITAL, VLC, etc.)
4. Click "Add FFT Node" to create the audio-reactive node
5. Connect the node's "Value" output to animate objects

### Manual Driver Setup (Recommended)
The custom node outputs have limitations, so manual drivers work best:

1. Right-click any animatable property (location, rotation, scale)
2. Select "Add Driver"
3. In the driver expression field, enter:
   ```python
   bpy.context.scene.get("fft_bin_0", 0) * 2
   ```
4. Replace `0` with desired frequency bin (0-15)
5. Adjust multiplier for desired effect intensity

### Frequency Bin Reference
- `fft_bin_0`: Sub Bass (20-60Hz) - Kick drums
- `fft_bin_1`: Bass (60-250Hz) - Bass lines
- `fft_bin_2`: Low Mid (250-500Hz) - Low vocals
- `fft_bin_3`: Mid (500-2kHz) - Vocals, instruments
- `fft_bin_4`: High Mid (2-4kHz) - Clarity, presence
- `fft_bin_5`: Presence (4-6kHz) - Vocal intelligibility
- `fft_bin_6`: Brilliance (6-20kHz) - Cymbals, hi-hats
- `fft_bin_7-15`: Higher frequency ranges

### Pre-calculated Instrument Properties
The addon now includes pre-calculated properties for common instruments and frequency bands:

**Instrument Presets:**
- `kick_drum` - Bins 0+1 (Sub Bass + Bass)
- `snare_drum` - Bins 4+5+6 (High Mid + Presence + Brilliance)
- `hi_hat` - Bins 6+7 (Brilliance range)
- `bass_line` - Bins 1+2 (Bass + Low Mid)
- `vocal_range` - Bins 3+4 (Mid + High Mid)

**Overall Metrics:**
- `overall_energy` - Sum of all bins (0-16 range)
- `overall_average` - Average of all bins (0-1 range)

**Frequency Band Groupings:**
- `sub_bass` - Bin 0 only (deepest frequencies)
- `bass` - Average of bins 1+2
- `mids` - Average of bins 3+4+5
- `highs` - Average of bins 6-15

**Usage examples:**
```python
# Kick drum scale
bpy.context.scene.get("kick_drum", 0) * 2

# Snare rotation
bpy.context.scene.get("snare_drum", 0) * 3.14

# Overall energy emission
bpy.context.scene.get("overall_average", 0) * 10

# Bass-driven position
bpy.context.scene.get("bass", 0) * 5
```

## Tips and Tricks

### For Better Low-End Response
- Low frequencies (kick drums) may appear weak in FFT
- Use higher multipliers for bins 0-2
- Try: `bpy.context.scene.get("fft_bin_0", 0) * 5`
- Consider using Math nodes in Geometry Nodes to boost specific ranges

### Performance Optimization
- Use 16 bins (default) for good balance of detail vs performance
- Close pavucontrol after setup to reduce CPU usage
- Stop capture when not needed to free audio resources

### Working with Different Audio Sources
- **Music Production (VITAL, Ableton)**: Clean signal, good for precise animation
- **Media Players (VLC, Spotify)**: Consistent levels, good for general use
- **Games**: Variable audio levels, may need normalization
- **Surge XT**: Note: May produce background "phantom noise" - this is normal

### Driver Limitations
- **Node Duplication**: Drivers are lost when duplicating custom nodes
- **Workaround**: Use Copy/Paste instead of duplicate (Ctrl+C, Ctrl+V)
- **Alternative**: Create drivers manually as they're more reliable

## Troubleshooting

### No Audio Detected
- Check pavucontrol: ensure Blender input is set to monitor device
- Verify audio is playing in source application
- Click "List Audio Devices" to see available inputs
- Try different audio applications

### High CPU Usage
- Reduce TIMER_INTERVAL in addon code (increase from 0.05 to 0.1)
- Use fewer frequency bins if possible
- Close unnecessary audio applications

### Crashes/Segfaults
- Usually caused by audio driver conflicts
- Restart Blender and try different audio source
- Update audio drivers
- Try different BLOCK_SIZE values (1024, 2048, 4096)

### Drivers Not Working
- Ensure correct syntax: `bpy.context.scene.get("fft_bin_X", 0)`
- Check that audio capture is started
- Verify property names in Outliner → Scene Properties

## Technical Details

- **Sample Rate**: 44.1kHz
- **Block Size**: 1024 samples (adjustable)
- **Frequency Bins**: 16 with logarithmic spacing
- **Update Rate**: ~20Hz (50ms intervals)
- **Supported Node Trees**: Shader, Compositor, Geometry Nodes
- **Dependencies**: NumPy, PyAudio

## Known Limitations

- Custom node outputs don't propagate values reliably (Blender limitation)
- Manual drivers are more stable than node connections
- Some synthesizers (like Surge XT) produce background noise
- Audio device switching requires addon restart
- Windows may need additional audio routing software

## Contributing

Contributions welcome! Areas for improvement:
- Better cross-platform audio device detection
- More robust node output implementation
- UI enhancements and presets
- Performance optimizations

## License

MIT License - Feel free to modify and distribute.

## Credits

- Original concept: GPT-assisted development
- Enhanced and debugged by: Claude AI
- Audio processing: NumPy, PyAudio
- Blender integration: Blender Python API

## Support

For issues and questions:
- Check troubleshooting section first
- Include system info (OS, Blender version, audio hardware)
- Provide console output for crashes
- Test with different audio sources

---

**Enjoy creating audio-reactive animations in Blender!**