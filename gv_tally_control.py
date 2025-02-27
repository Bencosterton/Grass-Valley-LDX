#!/usr/bin/env python3
"""
Grass Valley LDK Gateway Tally Control

This script provides a simple interface to control tally lights on 
Grass Valley LDK Gateway camera systems using XML commands.
"""

import socket
import argparse
import logging
import sys
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('gv_tally_control')

# Constants
DEFAULT_IP = "10.10.126.51"
DEFAULT_PORT = 8080

# Map XCU names to their respective session IDs
XCU_SESSION_IDS = {
    "XCU-08": "PH1XQE",
    "XCU-09": "9VDA4O",
    "XCU-10": "8KXCNL"
}

# Default session ID if XCU not found in the mapping
DEFAULT_SESSION_ID = "9VDA4O"

# Function IDs for different tally types
FUNCTION_IDS = {
    "red": "8215",
    "green": "8216",
    "yellow": "8217"
}

def format_authentication_request(name="TallySender"):
    """
    Format the XML authentication request.
    
    Args:
        name: Application name to use for authentication
        
    Returns:
        str: Formatted XML authentication request
    """
    return (
        f'<?xml version="2.0" encoding="UTF-8"?>\n'
        f'<application-authentication-request xml-protocol="2.0">\n'
        f'  <Name>{name}</Name>\n'
        f'</application-authentication-request>'
    )

def format_tally_command(session_id, function_id, value):
    """
    Format the XML tally command.
    
    Args:
        session_id: Session ID for the camera
        function_id: Function ID for the tally type
        value: "1" for ON, "0" for OFF
        
    Returns:
        str: Formatted XML tally command
    """
    return (
        f'<?xml version="2.0" encoding="UTF-8"?>\n'
        f'<function-value-change>\n'
        f'  <device>\n'
        f'    <sessionid>{session_id}</sessionid>\n'
        f'    <function id="{function_id}">\n'
        f'      <Value>{value}</Value>\n'
        f'    </function>\n'
        f'  </device>\n'
        f'</function-value-change>'
    )

def send_command(ip, port, xml_command, timeout=2):
    """
    Send an XML command to the Grass Valley LDK Gateway.
    
    Args:
        ip: IP address of the gateway
        port: Port number of the gateway
        xml_command: XML command to send
        timeout: Socket timeout in seconds
        
    Returns:
        str: Response from the gateway
    """
    logger.info(f"Connecting to {ip}:{port} via socket")
    
    # Create socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    
    try:
        # Connect to the gateway
        s.connect((ip, port))
        
        # Send the command
        logger.info("Sending command via socket")
        logger.debug(f"Command: {xml_command}")
        s.sendall(xml_command.encode('utf-8'))
        
        # Receive the response
        try:
            response = s.recv(4096).decode('utf-8')
            logger.debug(f"Response: {response}")
            return response, s
        except socket.timeout:
            logger.warning("Socket timeout while receiving response")
            return "", s
            
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        s.close()
        return "", None

def control_tally(ip, port, xcu_name, tally_type, state):
    """
    Control a tally light.
    
    Args:
        ip: IP address of the gateway
        port: Port number of the gateway
        xcu_name: XCU device name (e.g., XCU-09)
        tally_type: Type of tally (red, green, yellow)
        state: Desired state (on, off)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the session ID for the specified XCU
    session_id = XCU_SESSION_IDS.get(xcu_name, DEFAULT_SESSION_ID)
    logger.info(f"Using session ID {session_id} for {xcu_name}")
    
    # Validate tally type
    if tally_type not in FUNCTION_IDS:
        logger.error(f"Invalid tally type: {tally_type}. Must be one of: {', '.join(FUNCTION_IDS.keys())}")
        return False
    
    # Validate state
    if state.lower() not in ["on", "off"]:
        logger.error(f"Invalid state: {state}. Must be 'on' or 'off'")
        return False
    
    # Convert state to value
    value = "1" if state.lower() == "on" else "0"
    
    # Send authentication request
    logger.info("Sending authentication request...")
    auth_xml = format_authentication_request()
    auth_response, socket = send_command(ip, port, auth_xml)
    
    if socket is None:
        logger.error("Failed to connect to gateway")
        return False
    
    # Check for successful authentication
    # The gateway might not send a response immediately, or might send it after the next command
    # We'll consider it successful if we don't get an error
    if auth_response and "result=\"Ok\"" not in auth_response:
        logger.error(f"Authentication failed: {auth_response}")
        socket.close()
        return False
    
    logger.info("Authentication request sent")
    
    # Small delay to ensure authentication is processed
    time.sleep(0.5)
    
    # Send tally command using the same socket
    logger.info(f"Sending {tally_type} tally {state} command to {xcu_name}...")
    tally_xml = format_tally_command(
        session_id=session_id,
        function_id=FUNCTION_IDS[tally_type],
        value=value
    )
    
    try:
        logger.debug(f"Tally command: {tally_xml}")
        socket.sendall(tally_xml.encode('utf-8'))
        
        try:
            tally_response = socket.recv(4096).decode('utf-8')
            logger.debug(f"Tally response: {tally_response}")
            
            # Check if the response contains either an OK or the authentication indication
            # (which sometimes comes after the tally command)
            if "result=\"Ok\"" in tally_response or "<application-authentication-indication" in tally_response:
                logger.info(f"Successfully set {tally_type} tally to {state}")
                result = True
            else:
                logger.error(f"Failed to set tally: {tally_response}")
                result = False
                
        except socket.timeout:
            logger.warning("Socket timeout while receiving tally response")
            # Assume success if we don't get an error response
            logger.info(f"Assuming {tally_type} tally set to {state} (no error response)")
            result = True
            
    except Exception as e:
        logger.error(f"Error sending tally command: {e}")
        result = False
        
    finally:
        # Close the socket
        socket.close()
        
    return result

def main():
    """Main function to parse arguments and control tally lights."""
    parser = argparse.ArgumentParser(description='Control Grass Valley LDK Gateway tally lights')
    
    parser.add_argument('--ip', default=DEFAULT_IP,
                        help=f'IP address of the gateway (default: {DEFAULT_IP})')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'Port number of the gateway (default: {DEFAULT_PORT})')
    parser.add_argument('--xcu', 
                        help='XCU device ID (e.g., XCU-09)')
    parser.add_argument('--session', 
                        help='Override session ID (normally determined automatically from XCU)')
    parser.add_argument('--red', choices=['on', 'off'],
                        help='Control red tally (program)')
    parser.add_argument('--green', choices=['on', 'off'],
                        help='Control green tally (preview)')
    parser.add_argument('--yellow', choices=['on', 'off'],
                        help='Control yellow tally')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--list-xcus', action='store_true',
                        help='List all known XCUs and their session IDs')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # List XCUs if requested
    if args.list_xcus:
        print("Known XCUs and their session IDs:")
        for xcu, session_id in XCU_SESSION_IDS.items():
            print(f"  {xcu}: {session_id}")
        return 0
    
    # Check if XCU is specified
    if not args.xcu and not args.session:
        parser.error("Either --xcu or --session is required when controlling tally lights")
    
    # Check if at least one tally control argument is provided
    if not (args.red or args.green or args.yellow):
        parser.error("At least one tally control argument (--red, --green, --yellow) is required")
    
    # Control tally lights
    success = True
    
    # If a session ID is explicitly provided, use it instead of looking it up
    xcu_name = args.xcu if args.xcu else "Custom"
    
    # If a session ID is explicitly provided, override the XCU mapping
    if args.session:
        # Create a temporary function to override the session ID lookup
        def control_with_session_override(ip, port, tally_type, state):
            logger.info(f"Using override session ID {args.session}")
            # Validate tally type
            if tally_type not in FUNCTION_IDS:
                logger.error(f"Invalid tally type: {tally_type}")
                return False
            
            # Send authentication request
            logger.info("Sending authentication request...")
            auth_xml = format_authentication_request()
            auth_response, socket = send_command(ip, port, auth_xml)
            
            if socket is None:
                logger.error("Failed to connect to gateway")
                return False
            
            # Check for successful authentication
            if auth_response and "result=\"Ok\"" not in auth_response:
                logger.error(f"Authentication failed: {auth_response}")
                socket.close()
                return False
            
            logger.info("Authentication request sent")
            
            # Small delay to ensure authentication is processed
            time.sleep(0.5)
            
            # Send tally command using the same socket
            logger.info(f"Sending {tally_type} tally {state} command with session ID {args.session}...")
            tally_xml = format_tally_command(
                session_id=args.session,
                function_id=FUNCTION_IDS[tally_type],
                value="1" if state.lower() == "on" else "0"
            )
            
            try:
                logger.debug(f"Tally command: {tally_xml}")
                socket.sendall(tally_xml.encode('utf-8'))
                
                try:
                    tally_response = socket.recv(4096).decode('utf-8')
                    logger.debug(f"Tally response: {tally_response}")
                    
                    if "result=\"Ok\"" in tally_response or "<application-authentication-indication" in tally_response:
                        logger.info(f"Successfully set {tally_type} tally to {state}")
                        result = True
                    else:
                        logger.error(f"Failed to set tally: {tally_response}")
                        result = False
                        
                except socket.timeout:
                    logger.warning("Socket timeout while receiving tally response")
                    logger.info(f"Assuming {tally_type} tally set to {state} (no error response)")
                    result = True
                    
            except Exception as e:
                logger.error(f"Error sending tally command: {e}")
                result = False
                
            finally:
                socket.close()
                
            return result
        
        # Use the override function
        if args.red:
            if not control_with_session_override(args.ip, args.port, "red", args.red):
                success = False
        
        if args.green:
            if not control_with_session_override(args.ip, args.port, "green", args.green):
                success = False
        
        if args.yellow:
            if not control_with_session_override(args.ip, args.port, "yellow", args.yellow):
                success = False
    else:
        # Use the standard control function with XCU mapping
        if args.red:
            if not control_tally(args.ip, args.port, xcu_name, "red", args.red):
                success = False
        
        if args.green:
            if not control_tally(args.ip, args.port, xcu_name, "green", args.green):
                success = False
        
        if args.yellow:
            if not control_tally(args.ip, args.port, xcu_name, "yellow", args.yellow):
                success = False
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
