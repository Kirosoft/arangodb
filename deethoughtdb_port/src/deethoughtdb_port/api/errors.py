from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ApiError(Exception):
    status_code: int
    error_num: int
    error_message: str

    def to_payload(self) -> dict:
        return {
            "error": True,
            "code": self.status_code,
            "errorNum": self.error_num,
            "errorMessage": self.error_message,
        }


def unknown_api_version(version: int, path: str) -> ApiError:
    return ApiError(
        status_code=404,
        error_num=404,
        error_message=f"unknown API version {version} for path '{path}'",
    )


def not_found(path: str) -> ApiError:
    return ApiError(
        status_code=404,
        error_num=404,
        error_message=f"no handler found for path '{path}'",
    )


def bad_request(message: str) -> ApiError:
    return ApiError(
        status_code=400,
        error_num=400,
        error_message=message,
    )
