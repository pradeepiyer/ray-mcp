#!/bin/bash
# Ray cleanup utility - cleans up Ray processes and state from the local system

echo "🧹 Starting Ray cleanup..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to kill Ray processes by name
kill_ray_processes() {
    local process_name="$1"
    local pids
    
    if command_exists pgrep; then
        pids=$(pgrep -f "$process_name" 2>/dev/null || true)
        # Filter out the current script and its parent process to avoid
        # killing the invoking shell or pytest runner
        script_pid="$$"
        parent_pid="$PPID"
        pids=$(echo "$pids" | grep -v "^${script_pid}$" | grep -v "^${parent_pid}$" || true)
    elif command_exists ps; then
        # Fallback for systems without pgrep
        pids=$(ps aux | grep "$process_name" | grep -v grep | awk '{print $2}' 2>/dev/null || true)
    else
        echo "⚠️  Warning: Cannot find pgrep or ps to kill Ray processes"
        return 1
    fi
    
    if [ -n "$pids" ]; then
        echo "🔍 Found $process_name processes: $pids"
        echo "$pids" | while read -r pid; do
            if [ -n "$pid" ] && [ "$pid" -gt 0 ]; then
                # Check if process still exists
                if kill -0 "$pid" 2>/dev/null; then
                    echo "🔄 Terminating process $pid..."
                    kill -TERM "$pid" 2>/dev/null || true
                    sleep 1
                    # Force kill if still running
                    if kill -0 "$pid" 2>/dev/null; then
                        echo "💀 Force killing process $pid..."
                        kill -KILL "$pid" 2>/dev/null || true
                    fi
                else
                    echo "ℹ️  Process $pid already terminated"
                fi
            fi
        done
    else
        echo "✅ No $process_name processes found"
    fi
}

# Function to clean up Ray temporary directories
cleanup_ray_dirs() {
    local ray_dirs=(
        "/tmp/ray"
        "/tmp/ray_session_*"
        "$HOME/.ray"
        "/tmp/ray_cluster_*"
    )
    
    for dir_pattern in "${ray_dirs[@]}"; do
        if [ -d "$dir_pattern" ] 2>/dev/null; then
            echo "🗑️  Removing Ray directory: $dir_pattern"
            rm -rf "$dir_pattern" 2>/dev/null || true
        fi
    done
    
    # Also clean up any ray-related files in /tmp
    find /tmp -name "*ray*" -type f -delete 2>/dev/null || true
    find /tmp -name "*ray*" -type d -empty -delete 2>/dev/null || true
}

# Function to clean up Ray ports
cleanup_ray_ports() {
    local ray_ports=(6379 8265 10001 8000 8001 8002 8003 8004 8005)
    
    if command_exists lsof; then
        for port in "${ray_ports[@]}"; do
            local pids
            pids=$(lsof -ti:$port 2>/dev/null || true)
            if [ -n "$pids" ]; then
                echo "🔌 Killing processes using Ray port $port: $pids"
                echo "$pids" | while read -r pid; do
                    if [ -n "$pid" ] && [ "$pid" -gt 0 ]; then
                        if kill -0 "$pid" 2>/dev/null; then
                            kill -TERM "$pid" 2>/dev/null || true
                        fi
                    fi
                done
            fi
        done
    else
        echo "⚠️  Warning: lsof not available, cannot clean up Ray ports"
    fi
}

# Function to run Python Ray cleanup
run_python_cleanup() {
    if command_exists python3; then
        echo "🐍 Running Python Ray cleanup..."
        python3 -c "
import sys
import subprocess
import os

try:
    import ray
    if ray.is_initialized():
        print('🔄 Shutting down Ray from Python...')
        ray.shutdown()
        print('✅ Ray shutdown completed')
    else:
        print('✅ Ray not initialized in Python')
except ImportError:
    print('ℹ️  Ray not installed in Python')
except Exception as e:
    print(f'⚠️  Error during Python Ray cleanup: {e}')
" 2>/dev/null || true
    else
        echo "⚠️  Warning: Python3 not available for Ray cleanup"
    fi
}

# Function to clean up Ray using ray stop command
run_ray_stop() {
    if command_exists ray; then
        echo "🛑 Running 'ray stop' command..."
        ray stop 2>/dev/null || true
    else
        echo "ℹ️  Ray CLI not available"
    fi
}

# Main cleanup process
echo "🔍 Checking for Ray processes..."

# First try the official ray stop command
run_ray_stop

# Kill common Ray process names
kill_ray_processes "ray"
kill_ray_processes "raylet"
kill_ray_processes "plasma_store"
kill_ray_processes "gcs_server"
kill_ray_processes "dashboard"

# Clean up Ray ports
echo "🔌 Cleaning up Ray ports..."
cleanup_ray_ports

# Run Python cleanup
run_python_cleanup

# Clean up Ray directories
echo "🗂️  Cleaning up Ray directories..."
cleanup_ray_dirs

# Additional cleanup for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected - additional cleanup..."
    # Kill any remaining Ray processes using pkill
    if command_exists pkill; then
        pkill -f "ray" 2>/dev/null || true
        pkill -f "raylet" 2>/dev/null || true
    fi
fi

# Wait a moment for processes to fully terminate
sleep 2

# Final check for any remaining Ray processes
echo "🔍 Final check for remaining Ray processes..."
if command_exists pgrep; then
    remaining=$(pgrep -f "ray" 2>/dev/null || true)
    if [ -n "$remaining" ]; then
        # Filter out valid processes that might match "ray" but aren't Ray processes
        filtered_remaining=""
        echo "$remaining" | while read -r pid; do
            if [ -n "$pid" ] && [ "$pid" -gt 0 ]; then
                if kill -0 "$pid" 2>/dev/null; then
                    # Check if this is actually a Ray process
                    if ps -p "$pid" -o command= 2>/dev/null | grep -q "ray"; then
                        if [ -z "$filtered_remaining" ]; then
                            filtered_remaining="$pid"
                        else
                            filtered_remaining="$filtered_remaining $pid"
                        fi
                    fi
                fi
            fi
        done
        
        if [ -n "$filtered_remaining" ]; then
            echo "⚠️  Warning: Some Ray processes may still be running: $filtered_remaining"
        else
            echo "✅ No remaining Ray processes found"
        fi
    else
        echo "✅ No remaining Ray processes found"
    fi
fi

echo "✅ Ray cleanup completed!"
