#!/usr/bin/env python3
import os
import sys
import time
import socket
import threading
import logging
import re
import csv
from lxml import etree as ET
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
import requests
import json

# Default GV Gateway settings
DEFAULT_IP = ""
DEFAULT_PORT = 8080

# gateway_config.csv file path
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'gateway_config.csv')

# log all commands
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('gv_command_server')

app = Flask(__name__)

# Some variables
gateway_ip = None
gateway_port = None
last_auth_time = None
auth_interval = 60 
command_history = []
active_socket = None
auth_thread = None
auth_running = False

# load the gatewway config from csv file
def load_gateway_config():
    global gateway_ip, gateway_port
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                reader = csv.DictReader(f)
                config = next(reader)
                gateway_ip = config.get('ip', DEFAULT_IP)
                gateway_port = int(config.get('port', DEFAULT_PORT))
        else:
            gateway_ip = DEFAULT_IP
            gateway_port = DEFAULT_PORT
            save_gateway_config()
    except Exception as e:
        logger.error(f"Error loading gateway config: {e}")
        gateway_ip = DEFAULT_IP
        gateway_port = DEFAULT_PORT

def save_gateway_config():
    """Save gateway configuration to CSV file"""
    try:
        # If file doesn't exist, make file
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        with open(CONFIG_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ip', 'port'])
            writer.writeheader()
            writer.writerow({'ip': gateway_ip, 'port': gateway_port})
        logger.info(f"Gateway config saved successfully: {gateway_ip}:{gateway_port}")
        return True
    except Exception as e:
        logger.error(f"Error saving gateway config: {e}")
        return False

def send_command(ip, port, xml_command, timeout=2, buffer_size=8192):
    """Send an XML command to the gateway and return the response and socket"""
    sock = None
    try:
        if not ip or not port or not xml_command:
            logger.error("Invalid parameters for send_command")
            return None, None

        # socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # use gateway ip and port
        try:
            sock.connect((ip, port))
        except socket.timeout:
            logger.error(f"Connection timeout while connecting to {ip}:{port}")
            return None, None
        except socket.error as e:
            logger.error(f"Socket error while connecting to {ip}:{port}: {e}")
            return None, None

        # send command
        try:
            sock.sendall(xml_command.encode('utf-8'))
        except socket.error as e:
            logger.error(f"Error sending command to {ip}:{port}: {e}")
            return None, None

        # get a response
        response = ''
        try:
            while True:
                chunk = sock.recv(buffer_size)
                if not chunk:
                    break
                response += chunk.decode('utf-8')
                if response.count('<?xml') == response.count('>')\
                   and response.count('<') == response.count('>'):
                    break
        except socket.timeout:
            if not response:
                logger.error(f"Timeout while waiting for response from {ip}:{port}")
                return None, None
            logger.warning("Timeout while receiving complete response, using partial response")
        except socket.error as e:
            logger.error(f"Error receiving response from {ip}:{port}: {e}")
            return None, None

        if not response:
            logger.error(f"No response received from {ip}:{port}")
            return None, None

        return response, sock

    except Exception as e:
        logger.error(f"Unexpected error in send_command: {e}")
        return None, None

    finally:
        if sock and (not response or not sock):
            try:
                sock.close()
            except:
                pass

# a dino
#               __
#              / _)
#     _/\/\/\_/ /
#   _|         /
# _|  (  | (  |
#/__.-'|_|--|_|  |||||||


#This is the authentication command
def format_authentication_request(name="BCAN_GV_Command"):
    """Format the XML authentication request"""
    return (
        f'<?xml version="2.0" encoding="UTF-8"?>\n'
        f'<application-authentication-request xml-protocol="2.0">\n'
        f'  <name>{name}</name>\n'
        f'</application-authentication-request>'
    )

# and this is the control command
def format_command_template(session_id, function_id, value):
    """Format a command template for the given function"""
    return (
        f'<?xml version="2.0" encoding="UTF-8"?>\n'
        f'<function-value-change>\n'
        f'  <device>\n'
        f'    <deviceid>{session_id}</deviceid>\n'
        f'    <function id="{function_id}">\n'
        f'      <Value>{value}</Value>\n'
        f'    </function>\n'
        f'  </device>\n'
        f'</function-value-change>'
    )

def authenticate_gateway():
    """Send authentication request to the gateway"""
    global last_auth_time, active_socket
    
    if not gateway_ip or not gateway_port:
        logger.error("Authentication failed - IP or port not configured")
        return False
    
    logger.info(f"Authenticating with gateway at {gateway_ip}:{gateway_port}")
    
    # Format authentication request
    auth_xml = format_authentication_request(name="BCAN_GV_Command")
    
    try:
        # Close any existing socket first
        if active_socket:
            try:
                active_socket.close()
            except Exception as e:
                logger.warning(f"Error closing existing socket: {e}")
            active_socket = None
        
        # Send authentication request
        response, socket = send_command(gateway_ip, gateway_port, auth_xml)
        
        if not socket:
            logger.error("Authentication failed - could not establish connection")
            return False
        
        if not response:
            logger.error("Authentication failed - no response received")
            socket.close()
            return False
        
        # error check
        try:
            root = ET.fromstring(response)
            if root.tag == 'error':
                error_msg = root.text or 'Unknown error'
                logger.error(f"Authentication failed - gateway error: {error_msg}")
                socket.close()
                return False
        except ET.ParseError:
            logger.warning("Could not parse authentication response as XML")
        
        # Store sock with updated auth time
        active_socket = socket
        last_auth_time = datetime.now()
        
        # add command to history
        command_history.append({
            'timestamp': last_auth_time.strftime('%Y-%m-%d %H:%M:%S'),
            'command': auth_xml,
            'response': response,
            'type': 'authentication'
        })
        
        # only keep last 100 commands in history
        if len(command_history) > 100:
            command_history.pop(0)
            
        logger.info(f"Authentication successful at {last_auth_time}")
        return True
            
    except socket.timeout:
        logger.error("Authentication failed - connection timed out")
        return False
    except socket.error as e:
        logger.error(f"Authentication failed - socket error: {e}")
        return False
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False
    finally:
        if not active_socket and socket:
            try:
                socket.close()
            except:
                pass

def authentication_thread():
    """Background thread to periodically authenticate with the gateway"""
    global auth_running
    
    logger.info("Starting authentication thread")
    auth_running = True
    auth_failures = 0
    max_failures = 3  
    
    while auth_running:
        try:
            # check resposne fro auth
            if not gateway_ip or not gateway_port:
                logger.warning("Gateway not configured, waiting for configuration...")
                time.sleep(5)
                continue
            
            current_time = datetime.now()
            
            if last_auth_time is None or \
               (current_time - last_auth_time).total_seconds() >= auth_interval:
                
                if authenticate_gateway():
                    auth_failures = 0 # if a successful auth makes it though, reset failure counter
                else:
                    auth_failures += 1
                    logger.warning(f"Authentication failed {auth_failures} time(s) in a row")
                    
                    if auth_failures >= max_failures:
                        logger.error("Multiple authentication failures, increasing retry interval")
                        time.sleep(30)  
                        continue
            
            # Normal sleep between checks
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in authentication thread: {e}")
            time.sleep(5)  # Sleep on error to avoid tight loop
    
    logger.info("Authentication thread stopped")
    
    # Clean up socket on thread stop
    global active_socket
    if active_socket:
        try:
            active_socket.close()
        except:
            pass
        active_socket = None

def send_xml_command(xml_command, retries=3, delay=0.1):
    """Send an XML command to the gateway"""
    global active_socket
    
    for attempt in range(retries):
        # check if conneciton is active
        if active_socket is None:
            authenticate_gateway()
            
            if active_socket is None:
                return "Failed to establish connection to gateway", False
        
        try:
            logger.info("Sending custom XML command")
            logger.debug(f"Command: {xml_command}")
            
            active_socket.sendall(xml_command.encode('utf-8'))
            
            # resposne
            try:
                response = active_socket.recv(8192).decode('utf-8') 
                logger.debug(f"Response: {response}")
                
                # add to history
                command_history.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'command': xml_command,
                    'response': response,
                    'type': 'custom'
                })
                
                # only save 100 commands
                if len(command_history) > 100:
                    command_history.pop(0)
                    
                return response, True
                
            except socket.timeout:
                logger.warning(f"Socket timeout while receiving response (attempt {attempt + 1}/{retries})")
                active_socket = None  # force retry auth
                if attempt < retries - 1:
                    time.sleep(delay)  
                continue
                
        except Exception as e:
            logger.error(f"Error sending command (attempt {attempt + 1}/{retries}): {e}")
            active_socket = None  #force rery auth
            if attempt < retries - 1:
                time.sleep(delay)  
            continue
    
    return "Failed after all retries", False

@app.route('/')
def index():
    """Render the main page"""
    return render_template('gv_command.html', gateway_ip=gateway_ip, gateway_port=gateway_port)

@app.route('/api/gateway_config', methods=['GET'])
def api_get_gateway_config():
    """API endpoint to get current gateway configuration"""
    return jsonify({
        'ip': gateway_ip,
        'port': gateway_port
    })

@app.route('/api/gateway_config', methods=['POST'])
def api_set_gateway_config():
    """API endpoint to update gateway configuration"""
    global gateway_ip, gateway_port
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    if 'ip' not in data or 'port' not in data:
        return jsonify({'success': False, 'message': 'Both IP and port are required'})
    
    ip = data['ip'].strip()
    if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
        return jsonify({'success': False, 'message': 'Invalid IP address format'})

    try:
        port = int(data['port'])
        if port < 1 or port > 65535:
            return jsonify({'success': False, 'message': 'Port must be between 1 and 65535'})
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid port number'})
    
    gateway_ip = ip
    gateway_port = port
    
    if not save_gateway_config():
        return jsonify({'success': False, 'message': 'Failed to save configuration'})
    
    success = authenticate_gateway()
    if not success:
        return jsonify({'success': False, 'message': 'Failed to authenticate with new settings'})
    
    logger.info(f"Gateway configuration updated and authenticated successfully: {ip}:{port}")
    return jsonify({
        'success': True,
        'message': 'Configuration saved and authenticated successfully',
        'ip': gateway_ip,
        'port': gateway_port
    })

def load_function_ids():
    """Load function IDs from the summary file"""
    function_ids = {
        'Camera': {},
        'Basestation': {},
        'OCP': {}
    }
    
    current_section = None
    summary_file = os.path.join(os.path.dirname(__file__), 'function_ids_summary.txt')
    
    try:
        with open(summary_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Skip the main header
                if line.startswith('# Grass Valley'):
                    continue
                    
                # Check for section headers
                if line.startswith('## '):
                    if '1. Camera Functions' in line:
                        current_section = 'Camera'
                        continue
                    elif '2. Basestation Functions' in line:
                        current_section = 'Basestation'
                        continue
                    elif '3. OCP Functions' in line:
                        current_section = 'OCP'
                        continue
                
                # Process function definitions
                if current_section and ':' in line:
                    try:
                        name, id_str = line.split(':', 1)
                        name = name.strip()
                        function_id = int(id_str.strip())
                        function_ids[current_section][name] = function_id
                        logger.debug(f"Loaded function {name} ({function_id}) for {current_section}")
                    except ValueError as e:
                        logger.warning(f"Invalid function definition: {line} - {e}")
                    
        logger.info(f"Loaded {sum(len(funcs) for funcs in function_ids.values())} functions")
        return function_ids
    except Exception as e:
        logger.error(f"Error loading function IDs: {e}")
        return None

@app.route('/api/functions', methods=['GET'])
def api_get_functions():
    """API endpoint to get available functions for each device type"""
    try:
        device_type = request.args.get('type')
        function_ids = load_function_ids()
        
        if not function_ids:
            return jsonify({
                'success': False,
                'error': 'Failed to load function IDs'
            })
        
        # If a specific device type is requested
        if device_type:
            # Convert to title case to match our internal format
            device_type = device_type.title()
            
            if device_type in function_ids:
                # Sort functions by name for better organization
                sorted_functions = sorted(function_ids[device_type].items())
                
                functions = [
                    {
                        'id': function_id,
                        'name': name,
                        'template': format_command_template(
                            session_id='${deviceId}',
                            function_id=function_id,
                            value='${value}'
                        )
                    }
                    for name, function_id in sorted_functions
                ]
                
                logger.debug(f"Returning {len(functions)} functions for {device_type}")
                return jsonify({
                    'success': True,
                    'functions': functions
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Unknown device type: {device_type}'
                })
        
        # Return all functions grouped by device type
        result = {}
        for device_type, functions in function_ids.items():
            result[device_type] = {
                name: {
                    'id': function_id,
                    'template': format_command_template(
                        session_id='${deviceId}',
                        function_id=function_id,
                        value='${value}'
                    )
                }
                for name, function_id in sorted(functions.items())
            }
            
        logger.debug(f"Returning all functions: {sum(len(funcs) for funcs in function_ids.values())} total")
        return jsonify({
            'success': True,
            'functions': result
        })
    except Exception as e:
        logger.error(f"Error getting functions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/send_command', methods=['POST'])
def api_send_command():
    """API endpoint to send a custom XML command"""
    xml_command = request.json.get('command', '')
    
    if not xml_command:
        return jsonify({'success': False, 'message': 'No command provided'})
    
    response, success = send_xml_command(xml_command, retries=3, delay=0.1)
    
    return jsonify({
        'success': success,
        'response': response
    })

@app.route('/api/authenticate', methods=['POST'])
def api_authenticate():
    """API endpoint to manually trigger authentication"""
    success = authenticate_gateway()
    
    return jsonify({
        'success': success,
        'last_auth_time': last_auth_time.strftime('%Y-%m-%d %H:%M:%S') if last_auth_time else None
    })

# command history
@app.route('/api/history', methods=['GET'])
def api_history():
    return jsonify(command_history)

# gateway status
@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'connected': active_socket is not None,
        'gateway': f"{gateway_ip}:{gateway_port}",
        'last_auth_time': last_auth_time.strftime('%Y-%m-%d %H:%M:%S') if last_auth_time else None,
        'auth_running': auth_running
    })

# found devices
@app.route('/api/discover', methods=['GET', 'POST'])
def api_discover():
    try:
        if not gateway_ip:
            return jsonify({
                'success': False,
                'error': 'Gateway IP is not configured'
            })
        
        if request.method == 'POST':
            data = request.json or {}
            device_types = data.get('deviceTypes', [])
            start_num = data.get('startNum', 1)
            end_num = data.get('endNum', 12)
        else: 
            device_types = request.args.get('deviceTypes', '')
            device_types = [t.strip() for t in device_types.split(',')] if device_types else []
            start_num = request.args.get('startNum', 1)
            end_num = request.args.get('endNum', 12)
            
        if not device_types:
            device_types = ['Basestation', 'Camera', 'OCP']
            logger.debug("Using default device types")
            
        try:
            start_num = int(start_num)
            end_num = int(end_num)
            logger.debug(f"Using range: {start_num}-{end_num}")
        except (ValueError, TypeError):
            logger.error(f"Invalid range parameters: startNum={start_num}, endNum={end_num}")
            return jsonify({
                'success': False,
                'error': 'startNum and endNum must be integers'
            })
        
        # Validate parameters
        if not isinstance(start_num, int) or not isinstance(end_num, int):
            return jsonify({
                'success': False,
                'error': 'startNum and endNum must be integers'
            })
            
        if start_num < 1 or end_num < start_num:
            return jsonify({
                'success': False,
                'error': f'Invalid range: {start_num}-{end_num}'
            })
            
        # Validate device types
        valid_types = {'Camera', 'Basestation', 'OCP'}
        if not isinstance(device_types, list) or not device_types:
            return jsonify({
                'success': False,
                'error': 'deviceTypes must be a non-empty list'
            })
            
        # Check for invalid device types
        invalid_types = [t for t in device_types if t not in valid_types]
        if invalid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid device types: {invalid_types}. Must be one of: {list(valid_types)}'
            })
        
        logger.info(f"Starting device discovery: range {start_num}-{end_num}, types: {device_types}")
        
        discovered_devices = discover_devices(start_num, end_num, device_types)
        if discovered_devices is None:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch device information from gateway'
            })
        
        return jsonify({
            'success': True,
            'devices': discovered_devices
        })
        
    except ValueError as e:
        logger.error(f"Invalid request data: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid request data: {str(e)}'
        })
    except Exception as e:
        logger.error(f"Device discovery error: {e}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        })

@app.route('/api/test_discovery', methods=['GET'])
def test_device_discovery():
    """Test endpoint to verify device discovery"""
    try:
        if not gateway_ip:
            return jsonify({
                'success': False,
                'error': 'Gateway IP is not configured'
            })
            
        gateway_info = {
            'ip': gateway_ip,
            'port': gateway_port,
            'connected': active_socket is not None,
            'last_auth_time': last_auth_time.strftime('%Y-%m-%d %H:%M:%S') if last_auth_time else None
        }
            
        device_info = fetch_device_info()
        if not device_info:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch device information',
                'gateway_info': gateway_info
            })
            
        all_types = ['Camera', 'Basestation', 'OCP']
        discovered = discover_devices(1, 12, all_types)
        
        raw_counts = {
            'cameras': len(device_info.get('cameras', [])),
            'basestations': len(device_info.get('basestations', [])),
            'ocps': len(device_info.get('ocps', []))
        }
        
        discovered_counts = {}
        for device_type in all_types:
            discovered_counts[device_type] = len([d for d in discovered if d['type'] == device_type])
            
        discrepancies = []
        if raw_counts['cameras'] != discovered_counts['Camera']:
            discrepancies.append(f"Camera count mismatch: {raw_counts['cameras']} raw vs {discovered_counts['Camera']} discovered")
        if raw_counts['basestations'] != discovered_counts['Basestation']:
            discrepancies.append(f"Basestation count mismatch: {raw_counts['basestations']} raw vs {discovered_counts['Basestation']} discovered")
        if raw_counts['ocps'] != discovered_counts['OCP']:
            discrepancies.append(f"OCP count mismatch: {raw_counts['ocps']} raw vs {discovered_counts['OCP']} discovered")
        
        return jsonify({
            'success': True,
            'gateway_info': gateway_info,
            'raw_device_counts': raw_counts,
            'discovered_device_counts': discovered_counts,
            'total_discovered': len(discovered),
            'discrepancies': discrepancies,
            'raw_device_info': device_info,
            'discovered_devices': discovered
        })
    except requests.RequestException as e:
        logger.error(f"Network error in test device discovery: {e}")
        return jsonify({
            'success': False,
            'error': f'Network error: {str(e)}',
            'gateway_info': gateway_info if 'gateway_info' in locals() else None
        })
    except Exception as e:
        logger.error(f"Error in test device discovery: {e}")
        return jsonify({
            'success': False,
            'error': f'Test discovery error: {str(e)}',
            'gateway_info': gateway_info if 'gateway_info' in locals() else None
        })

# Parse the info from the gateway webserver about devices on network
def fetch_device_info():
    global gateway_ip
    
    if not gateway_ip:
        logger.error("Gateway IP is not configured")
        return None
    
    url = f'http://{gateway_ip}/home?ajax_c2ip&sub=c2ip_config'
    logger.info(f"Fetching device info from: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            logger.error(f"Failed to fetch device info. Status code: {response.status_code}")
            return None
            
        devices = response.json()
        logger.debug(f"Raw device data from gateway: {json.dumps(devices, indent=2)}")
        
        if not devices:
            logger.warning("No devices found in gateway response")
            return {
                "cameras": [],
                "basestations": [],
                "ocps": []
            }
        
        # list found devices by type
        cameras = []
        basestations = []
        ocps = []
        
        for device in devices:
            logger.debug(f"Processing device: {json.dumps(device, indent=2)}")
            
            device_type = device.get("52263", "")  # 52263 is the field for device type
            name = device.get("52265", "")         # 52265 is the field for device name
            device_id = device.get("52266", "")    # 52266 is the field for device ID
            
            logger.debug(f"Extracted fields - type: {device_type}, name: {name}, id: {device_id}")
            
            if not all([device_type, name, device_id]):
                logger.warning(f"Skipping device with missing fields: {device}")
                continue
            
            device_info = {
                "name": name,
                "id": device_id
            }
            
            device_type_map = {
                "Camera Head": "Camera",
                "Base Station": "Basestation",
                "OCP": "OCP"
            }
            
            #organise the devices by type
            normalized_type = device_type_map.get(device_type)
            if normalized_type:
                device_info['type'] = normalized_type
                
                if normalized_type == "Camera":
                    cameras.append(device_info)
                    logger.debug(f"Found camera: {name} (ID: {device_id})")
                elif normalized_type == "Basestation":
                    basestations.append(device_info)
                    logger.debug(f"Found basestation: {name} (ID: {device_id})")
                elif normalized_type == "OCP":
                    ocps.append(device_info)
                    logger.debug(f"Found OCP: {name} (ID: {device_id})")
            else:
                logger.warning(f"Unknown device type: {device_type} for device: {name}")
        
        result = {
            "cameras": cameras,
            "basestations": basestations,
            "ocps": ocps
        }
        
        logger.info(f"Found {len(cameras)} cameras, {len(basestations)} basestations, {len(ocps)} OCPs")
        return result
        
    except requests.RequestException as e:
        logger.error(f"Network error while fetching device info: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing device info JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in fetch_device_info: {e}")
        return None

def discover_devices(start_num, end_num, device_types):
    """Discover devices by querying the gateway's web interface"""
    discovered = []
    
    try:
        device_info = fetch_device_info()
        if not device_info:
            logger.warning("No device information returned from gateway")
            return discovered
            
        type_to_list = {
            'Camera': device_info.get('cameras', []),
            'Basestation': device_info.get('basestations', []),
            'OCP': device_info.get('ocps', [])
        }
        
        for device_type in device_types:
            if device_type in type_to_list:
                for device in type_to_list[device_type]:
                    device_info = {
                        "sessionId": "", # sessionid cannot be discovered from the web interface, but I tink deviceid will do
                        "name": device['name'],
                        "alias": device['name'],
                        "deviceId": device['id'],
                        "type": device_type,
                        "functions": {}
                    }
                    discovered.append(device_info)
                    logger.debug(f"Discovered {device_type}: {device['name']} (ID: {device['id']})")
            else:
                logger.warning(f"Unknown device type requested: {device_type}")
                
        if not discovered:
            logger.warning(f"No devices found matching requested types: {device_types}")
        else:
            logger.info(f"Discovered {len(discovered)} devices of types {device_types}")
            
    except Exception as e:
        logger.error(f"Error in device discovery: {e}")
        
    return discovered

def start_server(host='0.0.0.0', port=5000, debug=False):
    """Start the Flask server"""
    global auth_thread
    
    load_gateway_config()
    logger.info(f"Starting server with gateway at {gateway_ip}:{gateway_port}")

    # start auth
    auth_thread = threading.Thread(target=authentication_thread, daemon=True)
    auth_thread.start()
    
    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        global auth_running
        auth_running = False
        
        # close socket on app close
        if active_socket:
            try:
                active_socket.close()
            except Exception as e:
                logger.error(f"Error closing socket: {e}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Start the GV Command Server')
    parser.add_argument('--ip', default=DEFAULT_IP,
                        help=f'IP address of the gateway (default: {DEFAULT_IP})')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'Port number of the gateway (default: {DEFAULT_PORT})')
    parser.add_argument('--web-port', type=int, default=5000,
                        help='Port for the web server (default: 5000)')
    parser.add_argument('--auth-interval', type=int, default=60,
                        help='Authentication interval in seconds (default: 60)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    
    args = parser.parse_args()
    
    gateway_ip = args.ip
    gateway_port = args.port
    auth_interval = args.auth_interval
    
    logger.info(f"Starting GV Command Server")
    logger.info(f"Gateway: {gateway_ip}:{gateway_port}")
    logger.info(f"Web port: {args.web_port}")
    logger.info(f"Auth interval: {auth_interval} seconds")
    
    start_server(port=args.web_port, debug=args.debug)