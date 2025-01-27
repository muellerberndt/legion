from urllib.parse import urlparse
import os
from typing import Tuple


class AssetStorage:
    """Utility class for managing asset storage paths"""

    @staticmethod
    def get_asset_path(base_dir: str, source: str) -> Tuple[str, str]:
        """
        Generate storage path for an asset.

        Args:
            base_dir: Base directory for asset storage
            source: Source URL or local file path of the asset

        Returns:
            Tuple[str, str]: (target_directory, target_file)
        """
        # Check if source is a URL
        try:
            parsed_url = urlparse(source)
            if all([parsed_url.scheme, parsed_url.netloc]):
                # Handle URL paths
                path_components = [c for c in parsed_url.path.split("/") if c and c != "/"]
                target_dir = os.path.join(base_dir, parsed_url.netloc, *path_components)
                relative_path = os.path.join(parsed_url.netloc, *path_components)
            else:
                # Handle local file paths
                path_components = os.path.normpath(source).split(os.sep)
                # Take last two components of path (parent_dir/filename)
                path_components = path_components[-2:] if len(path_components) > 1 else path_components[-1:]
                target_dir = os.path.join(base_dir, *path_components)
                relative_path = os.path.join(*path_components)

        except Exception:
            # Handle local file paths on parse error
            path_components = os.path.normpath(source).split(os.sep)
            # Take last two components of path (parent_dir/filename)
            path_components = path_components[-2:] if len(path_components) > 1 else path_components[-1:]
            target_dir = os.path.join(base_dir, *path_components)
            relative_path = os.path.join(*path_components)

        # Verify the target_dir is under base_dir using realpath
        real_base = os.path.realpath(base_dir)
        real_target = os.path.realpath(target_dir)
        if not real_target.startswith(real_base):
            raise ValueError(f"Target directory {target_dir} is not under base directory {base_dir}")

        return target_dir, relative_path
