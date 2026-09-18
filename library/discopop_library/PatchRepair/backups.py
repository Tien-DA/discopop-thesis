# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.

"""Keeping the generated patches recoverable.

A repair overwrites files that ``discopop_patch_generator`` produced, so the pristine
version has to survive somewhere. The whole ``patch_generator/<id>/`` directory is
backed up, not just the files that happen to change: the applicator treats a
suggestion's patches as one indivisible unit, so a restore has to reproduce a coherent
set rather than a mixture of repaired and original files.
"""

import logging
import os
import shutil
from typing import List

logger = logging.getLogger("PatchRepair").getChild("backups")

BACKUPS_DIR_NAME = "backups"


def backups_dir(patch_repair_path: str) -> str:
    return os.path.join(patch_repair_path, BACKUPS_DIR_NAME)


def backup_patch_set(patch_repair_path: str, patch_generator_path: str, suggestion_id: int) -> str:
    """Copy a suggestion's pristine patch directory aside, once.

    A second call for the same suggestion is a no-op: the first backup is the pristine
    state, and overwriting it with an already-repaired set would destroy exactly what
    it exists to protect.
    """
    destination = os.path.join(backups_dir(patch_repair_path), str(suggestion_id))
    if os.path.exists(destination):
        logger.debug("Backup of suggestion " + str(suggestion_id) + " already exists; keeping it.")
        return destination
    source = os.path.join(patch_generator_path, str(suggestion_id))
    os.makedirs(backups_dir(patch_repair_path), exist_ok=True)
    shutil.copytree(source, destination)
    logger.debug("Backed up suggestion " + str(suggestion_id) + " to " + destination)
    return destination


def backed_up_suggestion_ids(patch_repair_path: str) -> List[int]:
    root = backups_dir(patch_repair_path)
    if not os.path.exists(root):
        return []
    return sorted(int(entry) for entry in os.listdir(root) if entry.isdigit())


def restore_patch_sets(patch_repair_path: str, patch_generator_path: str) -> List[int]:
    """Put every backed up patch set back and report which ones were restored."""
    restored: List[int] = []
    for suggestion_id in backed_up_suggestion_ids(patch_repair_path):
        source = os.path.join(backups_dir(patch_repair_path), str(suggestion_id))
        destination = os.path.join(patch_generator_path, str(suggestion_id))
        if os.path.exists(destination):
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        restored.append(suggestion_id)
        logger.info("Restored suggestion " + str(suggestion_id))
    return restored
