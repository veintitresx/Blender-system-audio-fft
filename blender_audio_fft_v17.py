bl_info = {
    "name": "System Audio FFT - User Friendly",
    "author": "veintitresx with Claude.ai (user-friendly)",
    "version": (0, 7),
    "blender": (4, 0, 0),
    "category": "Node",
    "location": "Node Editor > Sidebar > Audio FFT",
    "description": "User-friendly realtime FFT from system audio with dropdown selection",
}

import bpy
import time
import threading
import platform
from bpy.props import EnumProperty, FloatProperty

# Optional libs
try:
    import numpy as np
    import pyaudio
    DEPS_AVAILABLE = True
except ImportError:
    np = None
    pyaudio = None
    DEPS_AVAILABLE = False

# ---------- Config ----------
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
N_BINS = 16
TIMER_INTERVAL = 0.05
# ----------------------------

_pa = None
_stream = None
_running = False
_audio_thread = None
_fft_data = [0.0] * N_BINS
_audio_lock = threading.Lock()

def _ensure_audio_available():
    if not DEPS_AVAILABLE:
        raise RuntimeError("numpy and pyaudio are required")

def _cleanup_audio():
    global _pa, _stream
    try:
        if _stream is not None:
            if not _stream.is_stopped():
                _stream.stop_stream()
            _stream.close()
            _stream = None
    except Exception as e:
        print(f"Stream cleanup error: {e}")
    
    try:
        if _pa is not None:
            _pa.terminate()
            _pa = None
    except Exception as e:
        print(f"PyAudio cleanup error: {e}")

def _find_audio_device():
    try:
        if _pa is None:
            return None
            
        device_count = _pa.get_device_count()
        
        # Look for pulse/pipewire devices first
        for i in range(device_count):
            try:
                info = _pa.get_device_info_by_index(i)
                name = info['name'].lower()
                if ('pulse' in name or 'pipewire' in name) and info['maxInputChannels'] > 0:
                    print(f"Using audio device: {info['name']}")
                    return i
            except Exception:
                continue
        
        # Fallback to default
        try:
            default_info = _pa.get_default_input_device_info()
            print(f"Using default input: {default_info['name']}")
            return default_info['index']
        except Exception:
            pass
        
        return None
    except Exception as e:
        print(f"Device detection error: {e}")
        return None

def _safe_audio_loop():
    global _running, _fft_data, _pa, _stream
    
    try:
        _pa = pyaudio.PyAudio()
        device_index = _find_audio_device()
        
        if device_index is None:
            print("No suitable audio device found")
            return
        
        _stream = _pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=BLOCK_SIZE,
            start=False
        )
        
        _stream.start_stream()
        print("Audio stream started")
        
        while _running:
            try:
                if _stream.is_active():
                    data = _stream.read(BLOCK_SIZE, exception_on_overflow=False)
                    samples = np.frombuffer(data, dtype=np.float32)
                    
                    if len(samples) > 0:
                        # Apply smoothing window
                        windowed = samples * np.hanning(len(samples))
                        spectrum = np.abs(np.fft.rfft(windowed))
                        
                        # Logarithmic binning for better music representation
                        if len(spectrum) <= N_BINS:
                            binned = np.pad(spectrum, (0, N_BINS - len(spectrum)), 'constant')
                        else:
                            # Use log spacing for frequency bins
                            log_indices = np.logspace(0, np.log10(len(spectrum) - 1), N_BINS).astype(int)
                            log_indices = np.unique(log_indices)  # Remove duplicates
                            if len(log_indices) < N_BINS:
                                log_indices = np.linspace(0, len(spectrum) - 1, N_BINS).astype(int)
                            binned = spectrum[log_indices[:N_BINS]]
                        
                        # Smooth normalization to reduce jitter
                        max_val = binned.max()
                        if max_val > 0:
                            binned = binned / max_val
                            # Apply compression for better visualization
                            binned = np.power(binned, 0.6)
                        
                        # Apply temporal smoothing
                        with _audio_lock:
                            if any(_fft_data):  # If we have previous data
                                alpha = 0.3  # Smoothing factor
                                for i in range(min(len(binned), len(_fft_data))):
                                    _fft_data[i] = alpha * binned[i] + (1 - alpha) * _fft_data[i]
                            else:
                                _fft_data[:len(binned)] = binned.tolist()
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Audio processing error: {e}")
                time.sleep(0.1)
                
    except Exception as e:
        print(f"Audio thread error: {e}")
    finally:
        _cleanup_audio()

# ---------------- Improved Custom Node with Dropdown ----------------
def get_bin_items(self, context):
    """Generate dropdown items for frequency bins"""
    items = []
    freq_ranges = [
        "Sub Bass (20-60Hz)", "Bass (60-250Hz)", "Low Mid (250-500Hz)", "Mid (500-2kHz)",
        "High Mid (2-4kHz)", "Presence (4-6kHz)", "Brilliance (6-20kHz)", "Bin 7",
        "Bin 8", "Bin 9", "Bin 10", "Bin 11", "Bin 12", "Bin 13", "Bin 14", "Bin 15"
    ]
    
    for i in range(N_BINS):
        name = freq_ranges[i] if i < len(freq_ranges) else f"Bin {i}"
        items.append((str(i), name, f"Frequency bin {i}"))
    
    return items

class AUDIOFFT_Node(bpy.types.Node):
    """System Audio FFT Node with working outputs"""
    bl_idname = "AudioFFTNodeType"
    bl_label = "System Audio FFT"
    bl_icon = 'SPEAKER'
    bl_width_default = 200

    # Properties
    selected_bin: EnumProperty(
        name="Frequency Bin",
        description="Select which frequency bin to output",
        items=get_bin_items,
        default=0,
        update=lambda self, context: self.setup_output_driver()
    )
    
    smoothing: FloatProperty(
        name="Smoothing",
        description="Temporal smoothing amount",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )
    
    multiplier: FloatProperty(
        name="Multiplier",
        description="Scale the output value",
        default=1.0,
        min=0.0,
        max=10.0,
        update=lambda self, context: self.setup_output_driver()
    )

    def init(self, context):
        # Create output
        output = self.outputs.new('NodeSocketFloat', "Value")
        self.width = 250
        # Setup driver after creation
        self.setup_output_driver()

    def setup_output_driver(self):
        """Setup simple driver for the output socket"""
        if len(self.outputs) == 0:
            return
            
        output = self.outputs[0]
        
        # Remove existing driver
        try:
            output.driver_remove('default_value')
        except:
            pass
        
        # Add simple driver that only reads scene property
        try:
            fcurve = output.driver_add('default_value')
            driver = fcurve.driver
            driver.type = 'SCRIPTED'
            
            # Single variable for FFT data
            var = driver.variables.new()
            var.name = 'fft_val'
            var.type = 'SINGLE_PROP'
            target = var.targets[0]
            target.id_type = 'SCENE'
            target.id = bpy.context.scene
            target.data_path = f'["fft_bin_{self.selected_bin}"]'
            
            # Simple expression with multiplier hardcoded (since we can't reference node props)
            mult_val = self.multiplier
            driver.expression = f'fft_val * {mult_val} if fft_val != None else 0'
            
        except Exception as e:
            print(f"Failed to setup output driver: {e}")

    def draw_buttons(self, context, layout):
        """Draw node interface"""
        layout.prop(self, "selected_bin", text="")
        row = layout.row(align=True)
        row.prop(self, "smoothing", text="Smooth")
        row.prop(self, "multiplier", text="×")
        
        # Show current value
        scene = context.scene
        bin_idx = self.selected_bin
        raw_value = scene.get(f"fft_bin_{bin_idx}", 0.0)
        current_value = raw_value * self.multiplier
        layout.label(text=f"Live: {current_value:.3f}")
        
        # Show if connected
        if self.outputs[0].is_linked:
            layout.label(text="Connected ✓", icon='LINKED')
        else:
            layout.label(text="Not Connected", icon='UNLINKED')

    def update(self):
        """Update node"""
        pass

    def copy(self, node):
        """Called when node is duplicated"""
        bpy.app.timers.register(self.setup_output_driver, first_interval=0.1)

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname in {
            'ShaderNodeTree', 
            'CompositorNodeTree', 
            'GeometryNodeTree'
        }

# ---------------- Auto Driver Setup ----------------
class AUDIOFFT_OT_SetupDriver(bpy.types.Operator):
    """Setup driver for selected property"""
    bl_idname = "audiofft.setup_driver"
    bl_label = "Setup FFT Driver"
    bl_description = "Setup driver to animate selected property with FFT data"

    bin_index: bpy.props.IntProperty(default=0, min=0, max=N_BINS-1)

    def execute(self, context):
        # Get active object and property
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        
        # Define property paths that work with driver_add
        prop_path = "location"
        index = 2  # Z axis
        
        try:
            # Remove existing driver
            obj.driver_remove(prop_path, index)
        except:
            pass
        
        # Add new driver with separate path and index
        fcurve = obj.driver_add(prop_path, index)
        driver = fcurve.driver
        driver.type = 'SCRIPTED'
        
        # Add variable
        var = driver.variables.new()
        var.name = 'fft_val'
        var.type = 'SINGLE_PROP'
        
        target = var.targets[0]
        target.id_type = 'SCENE'
        target.id = context.scene
        target.data_path = f'["fft_bin_{self.bin_index}"]'
        
        # Set expression (this should work now)
        driver.expression = 'fft_val'
        
        self.report({'INFO'}, f"Driver setup for location.z using bin {self.bin_index}")
        return {'FINISHED'}

# ---------------- Original Operators (unchanged) ----------------
class AUDIOFFT_OT_Start(bpy.types.Operator):
    bl_idname = "audiofft.start"
    bl_label = "Start System Audio FFT"
    _timer = None

    def modal(self, context, event):
        global _running
        if not _running:
            return self.cancel(context)
            
        if event.type == 'TIMER':
            scene = context.scene
            scene['fft_timestamp'] = time.time()
            
            with _audio_lock:
                current_fft = _fft_data[:]
            
            for i, value in enumerate(current_fft):
                scene[f"fft_bin_{i}"] = float(value)
            
            # Pre-calculated instrument ranges
            scene['kick_drum'] = float(current_fft[0] + current_fft[1])
            scene['snare_drum'] = float(current_fft[4] + current_fft[5] + current_fft[6])
            scene['hi_hat'] = float(current_fft[6] + current_fft[7])
            scene['bass_line'] = float(current_fft[1] + current_fft[2])
            scene['vocal_range'] = float(current_fft[3] + current_fft[4])
            
            # Overall energy metrics
            total_energy = sum(current_fft)
            scene['overall_energy'] = float(total_energy)
            scene['overall_average'] = float(total_energy / len(current_fft))
            
            # Frequency band groupings
            scene['sub_bass'] = float(current_fft[0])
            scene['bass'] = float((current_fft[1] + current_fft[2]) / 2)
            scene['mids'] = float((current_fft[3] + current_fft[4] + current_fft[5]) / 3)
            scene['highs'] = float(sum(current_fft[6:]) / max(1, len(current_fft[6:])))
            
            # Update node tree
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        area.tag_redraw()
                
        return {'PASS_THROUGH'}

    def execute(self, context):
        global _running, _audio_thread
        
        if not DEPS_AVAILABLE:
            self.report({'ERROR'}, "numpy and pyaudio required")
            return {'CANCELLED'}
        
        if _running:
            self.report({'WARNING'}, "Already running")
            return {'CANCELLED'}
        
        scene = context.scene
        scene['fft_timestamp'] = 0.0
        for i in range(N_BINS):
            scene[f"fft_bin_{i}"] = 0.0
        
        _running = True
        _audio_thread = threading.Thread(target=_safe_audio_loop, daemon=True)
        _audio_thread.start()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(TIMER_INTERVAL, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, "Started audio capture")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        global _running
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        _running = False
        self.report({'INFO'}, "Stopped audio capture")
        return {'CANCELLED'}

class AUDIOFFT_OT_Stop(bpy.types.Operator):
    bl_idname = "audiofft.stop"
    bl_label = "Stop System Audio FFT"

    def execute(self, context):
        global _running
        _running = False
        return {'FINISHED'}

class AUDIOFFT_OT_CreateNode(bpy.types.Operator):
    bl_idname = "audiofft.create_node"
    bl_label = "Create FFT Node"

    def execute(self, context):
        if context.space_data.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Must be in Node Editor")
            return {'CANCELLED'}
        
        tree = context.space_data.edit_tree
        if tree is None:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}
        
        node = tree.nodes.new('AudioFFTNodeType')
        node.location = context.space_data.cursor_location
        
        self.report({'INFO'}, "FFT node created")
        return {'FINISHED'}

class AUDIOFFT_OT_TestDevices(bpy.types.Operator):
    bl_idname = "audiofft.test_devices"
    bl_label = "List Audio Devices"

    def execute(self, context):
        if not DEPS_AVAILABLE:
            self.report({'ERROR'}, "numpy and pyaudio required")
            return {'CANCELLED'}
        
        try:
            pa = pyaudio.PyAudio()
            print("\n=== Available Audio Devices ===")
            
            for i in range(pa.get_device_count()):
                try:
                    info = pa.get_device_info_by_index(i)
                    channels = info.get('maxInputChannels', 0)
                    if channels > 0:
                        print(f"[{i}] INPUT: {info['name']} ({channels} ch)")
                except Exception as e:
                    print(f"[{i}] Error: {e}")
            
            print("=== End Device List ===\n")
            pa.terminate()
            
            self.report({'INFO'}, "Device list printed to console")
        except Exception as e:
            self.report({'ERROR'}, f"Error: {e}")
        
        return {'FINISHED'}

# ---------------- Enhanced UI Panel ----------------
class AUDIOFFT_PT_Panel(bpy.types.Panel):
    bl_label = "System Audio FFT"
    bl_idname = "AUDIOFFT_PT_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Audio FFT'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Status and controls
        if _running:
            layout.label(text="Status: Recording", icon='REC')
            layout.operator('audiofft.stop', text='⏹ Stop', icon='PAUSE')
        else:
            layout.label(text="Status: Stopped", icon='PAUSE')
            layout.operator('audiofft.start', text='▶ Start', icon='PLAY')
        
        layout.separator()
        
        # Node creation
        layout.operator('audiofft.create_node', text='Add FFT Node', icon='NODE')
        layout.operator('audiofft.test_devices', text='List Devices', icon='OUTLINER_DATA_SPEAKER')
        
        layout.separator()
        
        # Quick driver setup
        box = layout.box()
        box.label(text="Quick Setup:", icon='DRIVER')
        if context.active_object:
            box.label(text=f"Object: {context.active_object.name}")
            row = box.row(align=True)
            for i in range(4):  # Show first 4 bins
                op = row.operator('audiofft.setup_driver', text=f"Bin {i}")
                op.bin_index = i
        else:
            box.label(text="Select an object first")
        
        # Live values preview
        if _running:
            box = layout.box()
            box.label(text="Live FFT Values:")
            
            with _audio_lock:
                current_fft = _fft_data[:]
            
            # Show in two columns
            col1 = box.column(align=True)
            col2 = box.column(align=True)
            
            for i in range(min(8, N_BINS)):
                value = current_fft[i] if i < len(current_fft) else 0.0
                col = col1 if i % 2 == 0 else col2
                col.label(text=f"Bin {i}: {value:.3f}")

# ---------------- Registration ----------------
classes = (
    AUDIOFFT_OT_Start,
    AUDIOFFT_OT_Stop,
    AUDIOFFT_OT_TestDevices,
    AUDIOFFT_OT_SetupDriver,
    AUDIOFFT_Node,
    AUDIOFFT_OT_CreateNode,
    AUDIOFFT_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    global _running
    _running = False
    _cleanup_audio()
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

if __name__ == "__main__":
    register()
