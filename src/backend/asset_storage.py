from urllib.parse import urlparse
import os
from typing import Tuple


class AssetStorage:
    """Utility class for managing asset storage paths"""

    @staticmethod
    def get_asset_path(base_dir: str, url: str) -> Tuple[str, str]:
        """
        Generate storage path for an asset.

        Args:
            base_dir: Base directory for asset storage
            url: Source URL of the asset

        Returns:
            Tuple[str, str]: (target_directory, relative_path)

        Raises:
            ValueError: If target directory would be outside base directory
        """
        parsed_url = urlparse(url)

        # Ensure path components don't start with slash
        path_components = [component for component in parsed_url.path.split("/") if component and component != "/"]

        # Construct target dir relative to base_dir
        target_dir = os.path.join(base_dir, parsed_url.netloc, *path_components)
        relative_path = os.path.join(parsed_url.netloc, *path_components)

        # Verify the target_dir is under base_dir using realpath
        real_base = os.path.realpath(base_dir)
        real_target = os.path.realpath(target_dir)
        if not real_target.startswith(real_base):
            raise ValueError(f"Target directory {target_dir} is not under base directory {base_dir}")

        return target_dir, relative_path
