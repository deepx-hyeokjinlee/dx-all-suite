"""
Docker Build Test Suite for dx-all-suite

This test suite validates Docker image builds for:
- dx-runtime (Ubuntu 24.04, 22.04, 20.04, 18.04, Debian 12)
- dx-modelzoo (Ubuntu 24.04, 22.04, 20.04, 18.04, Debian 12)
- dx-compiler (Ubuntu 24.04, 22.04, 20.04)

Total: 13 test cases
"""

import pytest
import subprocess
import os
import sys
from pathlib import Path

# Get project root (dx-all-suite directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
DOCKER_BUILD_SCRIPT = PROJECT_ROOT / "docker_build.sh"

# Test configuration
TEST_TIMEOUT = 1800  # 30 minutes per build


class TestDockerBuildSanity:
    """Sanity checks before running actual Docker builds"""
    
    def test_docker_build_script_exists(self):
        """Verify docker_build.sh script exists"""
        assert DOCKER_BUILD_SCRIPT.exists(), f"docker_build.sh not found at {DOCKER_BUILD_SCRIPT}"
    
    def test_docker_command_available(self):
        """Verify docker command is available"""
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "docker command not found"
    
    def test_docker_compose_command_available(self):
        """Verify docker compose command is available"""
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "docker compose command not found"
    
    def test_project_structure(self):
        """Verify essential project directories exist"""
        essential_dirs = [
            PROJECT_ROOT / "dx-compiler",
            PROJECT_ROOT / "dx-runtime",
            PROJECT_ROOT / "dx-modelzoo",
            PROJECT_ROOT / "docker",
        ]
        
        for dir_path in essential_dirs:
            assert dir_path.exists(), f"Essential directory not found: {dir_path}"


class TestDockerBuild:
    """Docker image build tests"""
    
    @pytest.mark.parametrize("target,os_type,version", [
        # dx-runtime tests (5 configurations)
        ("dx-runtime", "ubuntu", "24.04"),
        ("dx-runtime", "ubuntu", "22.04"),
        ("dx-runtime", "ubuntu", "20.04"),
        ("dx-runtime", "ubuntu", "18.04"),
        ("dx-runtime", "debian", "12"),
        
        # dx-modelzoo tests (5 configurations)
        ("dx-modelzoo", "ubuntu", "24.04"),
        ("dx-modelzoo", "ubuntu", "22.04"),
        ("dx-modelzoo", "ubuntu", "20.04"),
        ("dx-modelzoo", "ubuntu", "18.04"),
        ("dx-modelzoo", "debian", "12"),
        
        # dx-compiler tests (3 configurations - Ubuntu only)
        ("dx-compiler", "ubuntu", "24.04"),
        ("dx-compiler", "ubuntu", "22.04"),
        ("dx-compiler", "ubuntu", "20.04"),
    ])
    def test_docker_build(self, target, os_type, version):
        """
        Test Docker image build for specific target and OS version
        
        Args:
            target: Docker build target (dx-runtime, dx-modelzoo, dx-compiler)
            os_type: OS type (ubuntu or debian)
            version: OS version (24.04, 22.04, 20.04, 18.04, 12)
        """
        # Build command
        cmd = [
            str(DOCKER_BUILD_SCRIPT),
            f"--target={target}",
            f"--{os_type}_version={version}",
            "--internal",
            # "--skip-archive",  # Skip archiving to speed up tests
        ]
        
        print(f"\n{'='*80}")
        print(f"Testing: {target} on {os_type}:{version}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*80}\n")
        
        # Run build
        result = self.run_docker_build(cmd, target, os_type, version)
        
        # Assert build succeeded
        assert result.returncode == 0, (
            f"Docker build failed for {target} on {os_type}:{version}\n"
            f"Exit code: {result.returncode}\n"
            f"See logs above for details"
        )
    
    def run_docker_build(self, cmd, target, os_type, version):
        """
        Execute docker build command with real-time output
        
        Args:
            cmd: Command list to execute
            target: Build target name
            os_type: OS type
            version: OS version
            
        Returns:
            CompletedProcess object
        """
        try:
            # Run command with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=PROJECT_ROOT
            )
            
            # Print output in real-time
            output_lines = []
            for line in process.stdout:
                print(line, end='')
                output_lines.append(line)
            
            # Wait for completion
            process.wait(timeout=TEST_TIMEOUT)
            
            # Create result object
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=''.join(output_lines),
                stderr=None
            )
            
            return result
            
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail(
                f"Docker build timed out after {TEST_TIMEOUT} seconds for "
                f"{target} on {os_type}:{version}"
            )
        except Exception as e:
            pytest.fail(
                f"Docker build failed with exception for {target} on {os_type}:{version}: {str(e)}"
            )


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "sanity: marks tests as sanity checks (deselect with '-m \"not sanity\"')"
    )
    config.addinivalue_line(
        "markers", "runtime: marks tests as dx-runtime build tests"
    )
    config.addinivalue_line(
        "markers", "modelzoo: marks tests as dx-modelzoo build tests"
    )
    config.addinivalue_line(
        "markers", "compiler: marks tests as dx-compiler build tests"
    )


# Apply markers to test classes
TestDockerBuildSanity = pytest.mark.sanity(TestDockerBuildSanity)
