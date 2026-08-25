#!/usr/bin/env python3
"""
Combined server to serve frontend and handle API requests
"""

import http.server
import socketserver
import json
import os
from pathlib import Path
import sys
import urllib.parse

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import BenchmarkApp
from backend.benchmark_runner import BenchmarkRunner
from backend.mcp_client import MCPClient

# Initialize backend components
benchmark_app = BenchmarkApp()
benchmark_runner = BenchmarkRunner()
MCP_SERVER_COMMAND = (
    "/home/dinhtienvu/TU_Darmstadt/6.Semester/Thesis/"
    "discopop-thesis/venv/bin/discopop_mcp_server"
)

mcp_client = MCPClient(MCP_SERVER_COMMAND)

# Get port from command line argument or use default
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# Get the directory of this script
script_dir = Path(__file__).parent.absolute()

class CombinedHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        self.directory = script_dir / "frontend"
        super().__init__(*args, directory=self.directory, **kwargs)
    
    def do_POST(self):
        """Handle POST requests for API endpoints"""
        if self.path.startswith('/api/'):
            self.handle_api_request()
        else:
            # For other POST requests, fallback to default behavior
            super().do_POST()
    
    def handle_api_request(self):
        """Handle API requests"""
        try:
            # Get the content length
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Parse JSON data
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
            
            # Route based on path
            if self.path == '/api/connect':
                response = self.handle_connect(data)
            elif self.path == '/api/run_benchmark':
                response = self.handle_run_benchmark(data)
            else:
                self.send_response(404)
                self.end_headers()
                return
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def handle_connect(self, data):
        """Handle LLM connection request"""
        server_url = data.get('serverUrl')
        api_key = data.get('apiKey')
        model = data.get('model', 'gpt-4')
        
        if not server_url or not api_key:
            return {'error': 'Server URL and API key are required'}
            
        success = benchmark_app.connect_to_llm(server_url, api_key, model)
        
        return {
            'success': success,
            'message': 'Connected successfully!' if success else 'Connection failed!',
            'connection_info': benchmark_app.get_connection_info()
        }
    
    def handle_run_benchmark(self, data):
        """Handle benchmark run request"""
        task_type = data.get('taskType', 'general-coding')
        benchmark_case = data.get('benchmarkCase', 'fix-bug')
        runs = int(data.get('runs', 3))
        max_steps = int(data.get('maxSteps', 6))
        
        if not benchmark_app.is_connected():
            return {'error': 'Not connected to LLM server'}
            
        results = benchmark_app.run_benchmark({
            'task_type': task_type,
            'benchmark_case': benchmark_case,
            'runs': runs,
            'max_steps': max_steps
        })
        
        return results

    def do_GET(self):
        """Handle GET requests for API endpoints."""

        if self.path == '/api/mcp/tools':
            self.handle_mcp_tools()
            return

        super().do_GET()

    def handle_mcp_tools(self):
        """Return tools discovered from the DiscoPoP MCP server."""

        try:
            if not mcp_client.is_connected():
                success = mcp_client.connect()

                if not success:
                    self.send_response(500)
                    self.send_header(
                        'Content-type',
                        'application/json'
                    )
                    self.end_headers()

                    self.wfile.write(
                        json.dumps({
                            'error': 'Failed to connect to MCP server'
                        }).encode()
                    )

                    return

            tools = mcp_client.list_available_tools()

            self.send_response(200)
            self.send_header(
                'Content-type',
                'application/json'
            )
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    'success': True,
                    'tools': tools
                }).encode()
            )

        except Exception as exc:
            self.send_response(500)
            self.send_header(
                'Content-type',
                'application/json'
            )
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    'error': str(exc)
                }).encode()
            )

def main():
    print(f"Serving frontend files from {script_dir / 'frontend'}")
    print(f"Access the UI at: http://localhost:{PORT}")
    print("API endpoints:")
    print("  POST /api/connect - Connect to LLM")
    print("  POST /api/run_benchmark - Run benchmark")
    print("Press Ctrl+C to stop")
    
    try:
        with socketserver.TCPServer(("", PORT), CombinedHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"Port {PORT} is already in use. Please stop the existing process or use a different port.")
        else:
            print(f"Error starting server: {e}")

if __name__ == "__main__":
    main()