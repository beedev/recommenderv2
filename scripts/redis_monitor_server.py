#!/usr/bin/env python3
"""
Simple HTTP server for Redis monitoring dashboard
Usage: python scripts/redis_monitor_server.py
Access: http://localhost:8002
"""

import json
import redis
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

class RedisMonitorHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)

        # Serve the HTML dashboard
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            self.serve_html()

        # API endpoint for Redis data
        elif parsed_path.path == '/api/redis-data':
            self.serve_redis_data()

        else:
            self.send_error(404, "Not Found")

    def serve_html(self):
        """Serve the HTML dashboard"""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redis Monitor Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }

        .refresh-info {
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.9rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
            font-size: 0.85rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }

        .stat-sub {
            font-size: 0.9rem;
            color: #999;
            margin-top: 5px;
        }

        .sessions-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }

        .section-title {
            font-size: 1.5rem;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .session-card {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
        }

        .session-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .session-id {
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            color: #667eea;
            font-weight: bold;
        }

        .session-state {
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }

        .session-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }

        .detail-item {
            display: flex;
            flex-direction: column;
        }

        .detail-label {
            font-size: 0.75rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }

        .detail-value {
            font-size: 1rem;
            color: #333;
            font-weight: 500;
        }

        .components-list {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-top: 10px;
        }

        .component-item {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }

        .component-item:last-child {
            border-bottom: none;
        }

        .component-name {
            font-weight: bold;
            color: #667eea;
        }

        .loading {
            text-align: center;
            padding: 50px;
            color: white;
            font-size: 1.2rem;
        }

        .error {
            background: #ff4757;
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }

        .no-sessions {
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 1.1rem;
        }

        .ttl-warning {
            color: #ff4757;
            font-weight: bold;
        }

        .ttl-ok {
            color: #26de81;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Redis Session Monitor</h1>
            <div class="refresh-info">Auto-refreshing every 5 seconds</div>
        </div>

        <div id="content">
            <div class="loading">⏳ Loading Redis data...</div>
        </div>
    </div>

    <script>
        async function fetchRedisData() {
            try {
                const response = await fetch('/api/redis-data');
                const data = await response.json();

                if (data.error) {
                    showError(data.error);
                    return;
                }

                renderDashboard(data);
            } catch (error) {
                showError(error.message);
            }
        }

        function showError(message) {
            document.getElementById('content').innerHTML = `
                <div class="error">
                    <h2>❌ Error</h2>
                    <p>${message}</p>
                </div>
            `;
        }

        function renderDashboard(data) {
            const stats = data.redis_stats;
            const sessions = data.sessions;

            let html = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Active Sessions</div>
                        <div class="stat-value">${data.active_sessions}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Memory Usage</div>
                        <div class="stat-value">${stats.memory.used}</div>
                        <div class="stat-sub">Peak: ${stats.memory.peak}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Hit Rate</div>
                        <div class="stat-value">${stats.performance.hit_rate_percent}%</div>
                        <div class="stat-sub">Hits: ${stats.performance.keyspace_hits} | Misses: ${stats.performance.keyspace_misses}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Operations/Sec</div>
                        <div class="stat-value">${stats.performance.ops_per_sec}</div>
                    </div>
                </div>

                <div class="sessions-section">
                    <h2 class="section-title">Active Sessions (${sessions.length})</h2>
            `;

            if (sessions.length === 0) {
                html += '<div class="no-sessions">No active sessions found</div>';
            } else {
                sessions.forEach(session => {
                    const ttlClass = session.ttl_minutes < 10 ? 'ttl-warning' : 'ttl-ok';
                    const responseJson = session.response_json || {};

                    html += `
                        <div class="session-card">
                            <div class="session-header">
                                <div class="session-id">${session.session_id}</div>
                                <div class="session-state">${session.state}</div>
                            </div>
                            <div class="session-details">
                                <div class="detail-item">
                                    <div class="detail-label">Language</div>
                                    <div class="detail-value">${session.language}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Messages</div>
                                    <div class="detail-value">${session.message_count}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">TTL Remaining</div>
                                    <div class="detail-value ${ttlClass}">${session.ttl_minutes} min</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Created</div>
                                    <div class="detail-value">${new Date(session.created_at).toLocaleString()}</div>
                                </div>
                            </div>
                            <div class="components-list">
                                <div class="detail-label" style="margin-bottom: 10px;">Selected Components</div>
                                ${formatComponents(responseJson)}
                            </div>
                        </div>
                    `;
                });
            }

            html += '</div>';

            document.getElementById('content').innerHTML = html;
        }

        function formatComponents(responseJson) {
            let html = '';
            const components = ['PowerSource', 'Feeder', 'Cooler', 'Interconnector', 'Torch'];

            components.forEach(comp => {
                const item = responseJson[comp];
                if (item && item.name) {
                    html += `
                        <div class="component-item">
                            <span class="component-name">${comp}:</span> ${item.name}
                            ${item.gin ? ` <span style="color: #999;">(${item.gin})</span>` : ''}
                        </div>
                    `;
                } else {
                    html += `
                        <div class="component-item" style="color: #999;">
                            <span class="component-name">${comp}:</span> Not selected
                        </div>
                    `;
                }
            });

            const accessories = responseJson.Accessories || [];
            if (accessories.length > 0) {
                html += `
                    <div class="component-item">
                        <span class="component-name">Accessories:</span> ${accessories.length} items
                    </div>
                `;
            }

            return html;
        }

        // Initial load
        fetchRedisData();

        // Auto-refresh every 5 seconds
        setInterval(fetchRedisData, 5000);
    </script>
</body>
</html>"""

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

    def serve_redis_data(self):
        """Fetch Redis data and return as JSON"""
        try:
            # Connect to Redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

            # Get all session keys
            session_keys = r.keys("session:*")

            # Collect session details
            sessions = []
            for key in session_keys:
                session_id = key.replace("session:", "")
                session_json = r.get(key)

                if session_json:
                    session_data = json.loads(session_json)
                    ttl = r.ttl(key)

                    sessions.append({
                        "session_id": session_id,
                        "state": session_data.get('current_state', 'N/A'),
                        "language": session_data.get('language', 'N/A'),
                        "message_count": len(session_data.get('conversation_history', [])),
                        "ttl_seconds": ttl,
                        "ttl_minutes": round(ttl / 60, 1) if ttl > 0 else 0,
                        "created_at": session_data.get('created_at', 'N/A'),
                        "master_parameters": session_data.get('master_parameters', {}),
                        "response_json": session_data.get('response_json', {})
                    })

            # Get Redis memory info
            memory_info = r.info('memory')
            stats_info = r.info('stats')
            keyspace_info = r.info('keyspace')

            # Calculate hit rate
            hits = stats_info.get('keyspace_hits', 0)
            misses = stats_info.get('keyspace_misses', 0)
            total_ops = hits + misses
            hit_rate = round((hits / total_ops * 100), 2) if total_ops > 0 else 0

            # Build response
            response_data = {
                "timestamp": datetime.now().isoformat(),
                "active_sessions": len(sessions),
                "sessions": sessions,
                "redis_stats": {
                    "memory": {
                        "used": memory_info.get('used_memory_human', 'N/A'),
                        "peak": memory_info.get('used_memory_peak_human', 'N/A'),
                        "used_bytes": memory_info.get('used_memory', 0)
                    },
                    "performance": {
                        "ops_per_sec": stats_info.get('instantaneous_ops_per_sec', 0),
                        "keyspace_hits": hits,
                        "keyspace_misses": misses,
                        "hit_rate_percent": hit_rate
                    },
                    "keyspace": keyspace_info
                }
            }

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            error_response = {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())

def run_server(port=8002):
    """Run the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, RedisMonitorHandler)
    print(f"\n🚀 Redis Monitor Server running!")
    print(f"📊 Dashboard: http://localhost:{port}")
    print(f"🔌 API: http://localhost:{port}/api/redis-data")
    print("\n⏳ Auto-refreshes every 5 seconds")
    print("🛑 Press Ctrl+C to stop\n")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
