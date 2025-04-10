import sys
import io
import os
import fitz
import uuid
from typing import BinaryIO, Any


from ._html_converter import HtmlConverter
from ._llm_caption import llm_caption
from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE


# Try loading optional (but in this case, required) dependencies
# Save reporting of any exceptions for later
_dependency_exc_info = None
try:
    import fitz
except ImportError:
    # Preserve the error and stack trace for later
    _dependency_exc_info = sys.exc_info()


ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/pdf",
    "application/x-pdf",
]

ACCEPTED_FILE_EXTENSIONS = [".pdf"]


class PdfConverter(DocumentConverter):
    """
    Converts PDFs to Markdown. Most style information is ignored, so the results are essentially plain-text.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        image_save_dir: str = None,
        base_url: str = None,
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        # Check the dependencies
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="pdf",
                )
            ) from _dependency_exc_info[
                1
            ].with_traceback(  # type: ignore[union-attr]
                _dependency_exc_info[2]
            )

        if image_save_dir is None:
            image_save_dir = os.path.join(os.getcwd(), "pdf-images")

        os.makedirs(image_save_dir, exist_ok=True)

        pdf_data = file_stream.read()

        doc = fitz.open(stream=pdf_data, filetype="pdf")
        markdown_content = []
        image_info = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 페이지 구분
            markdown_content.append(f"\n\n<!-- Page {page_num + 1} -->\n")

            # 텍스트 추출
            text = page.get_text()
            markdown_content.append(text)

        if image_save_dir and base_url:
            # 이미지 추출
            image_list = page.get_images()
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)

                if base_image:
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    image_filename = f"pdf-image-{uuid.uuid4().hex[:8]}.{image_ext}"
                    image_path = os.path.join(image_save_dir, image_filename)

                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    llm_description = ""
                    llm_client = kwargs.get("llm_client")
                    llm_model = kwargs.get("llm_model")
                    if llm_client is not None and llm_model is not None:
                        try:
                            image_stream = io.BytesIO(image_bytes)
                            image_stream_info = StreamInfo(
                                mimetype=f"image/{image_ext}",
                                extension=image_ext,
                                filename=image_filename,
                            )
                            llm_description = llm_caption(
                                image_stream,
                                image_stream_info,
                                client=llm_client,
                                model=llm_model,
                                prompt=kwargs.get("llm_prompt"),
                            )
                        except Exception:
                            # 설명 생성 실패 시 처리
                            pass

                    if base_url:
                        rel_dir = os.path.basename(image_save_dir)
                        image_url = f"{base_url.rstrip('/')}/{rel_dir}/{image_filename}"
                    else:
                        image_url = image_path

                    image_info.append(
                        {
                            "url": image_url,
                            "page": page_num + 1,
                            "index": img_index + 1,
                            "filename": image_filename,
                            "path": image_path,
                            "type": base_image["ext"],
                        }
                    )

                    markdown_content.append(
                        f"{llm_description}\n![PqDF Image {page_num + 1}-{img_index + 1}]({image_url})\n"
                    )

        doc.close()
        return DocumentConverterResult(
            markdown="\n".join(markdown_content).strip(), images=image_info
        )
