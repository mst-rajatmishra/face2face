from __future__ import annotations
from typing import TYPE_CHECKING, Union, List, Tuple

from media_toolkit import ImageFile

# Type hinting for Face2Face class only during type checking
if TYPE_CHECKING:
    from face2face.core.face2face import Face2Face

# regular imports
import glob
import os
from io import BytesIO

import numpy as np
from insightface.app.common import Face

from face2face.core.modules.storage.f2f_loader import load_reference_face_from_file
from face2face.core.modules.storage.file_writable_face import FileWriteableFace
from face2face.settings import EMBEDDINGS_DIR
from face2face.core.modules.utils.utils import encode_path_safe
from face2face.core.modules.utils.utils import load_image


class _FaceEmbedding:
    def load_face(self: Face2Face, face_name: str) -> Union[List[Face], None]:
        """
        Load a reference face embedding from a file.
        :param face_name: the name of the reference face embedding
        :return: the embedding of the reference face(s)
        """
        # check if is already in RAM; if yes, return that one
        embedding = self._face_embeddings.get(face_name)
        if embedding is not None:
            return embedding

        # load from file
        file = os.path.join(self._face_embedding_folder, f"{face_name}.npz")
        embedding = load_reference_face_from_file(file)

        if embedding is None:
            raise ValueError(f"Reference face {face_name} not found. "
                             f"Please add the reference face first with add_reference_face")

        # Convert embedding to Face objects
        embedding = [Face(face) for face in embedding]

        # Add to memory dict
        self._face_embeddings[face_name] = embedding
        return embedding

    def load_faces(self, face_names: Union[str, List[str], List[Face], None] = None) -> dict:
        """
        Load specified faces from the _face_embeddings folder.
        :param face_names: A single name, list of names, or list of Face objects to load.
            If None, all stored face embeddings are loaded and returned.
        :return: Loaded faces as a dictionary: {face_name: face_embedding}.
        """
        if face_names is None:
            return self.load_all_faces()
        elif isinstance(face_names, str):
            return {face_names: self.load_face(face_names)}

        # Convert a list of faces to a dictionary
        return {
            face if isinstance(face, str) else i: self.load_face(face)
            for i, face in enumerate(face_names)
        }

    def load_all_faces(self: Face2Face) -> dict:
        """
        Load all face embeddings from the _face_embeddings folder.
        """
        for face_name in glob.glob(self._face_embedding_folder + "/*.npz"):
            self.load_face(face_name)
        return self._face_embeddings

    def add_face(
        self: Face2Face,
        face_name: str,
        image: Union[np.array, str, ImageFile],
        save: bool = False
    ) -> Tuple[str, np.array]:
        """
        Add a reference face to the face swapper. This face will be used for swapping in other images.
        :param face_name: The name for the reference face.
        :param image: The image from which to extract faces (can be a numpy array, file path, or ImageFile).
        :param save: If True, the reference face will be saved to the _face_embeddings folder for future use.
        :return: A tuple containing the safely encoded face name and the reference face.
        :raises ValueError: If face detection fails to find any faces in the image.
        """
        try:
            image = load_image(image)
            face_name = encode_path_safe(face_name)

            detected_faces = self.detect_faces(image)
            if not detected_faces:
                raise ValueError(f"No faces detected in the provided image for {face_name}.")

            self._face_embeddings[face_name] = detected_faces
            # Convert detected faces to FileWriteableFace
            save_able_ref_faces = [FileWriteableFace(face) for face in detected_faces]

            # Save face to virtual file
            virtual_file = BytesIO()
            np.save(virtual_file, arr=save_able_ref_faces, allow_pickle=True)
            virtual_file.seek(0)

            # Save to disk if required
            if save:
                os.makedirs(EMBEDDINGS_DIR, exist_ok=True)  # Ensure the directory exists
                filename = os.path.join(EMBEDDINGS_DIR, f"{face_name}.npz")

                if os.path.isfile(filename):
                    print(f"Reference face {face_name} already exists. Overwriting.")

                with open(filename, "wb") as f:
                    f.write(virtual_file.getbuffer())

            return face_name, virtual_file.getvalue()

        except Exception as e:
            print(f"Error while adding face: {e}")
            raise
