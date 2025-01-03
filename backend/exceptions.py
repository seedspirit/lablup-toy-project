class ChatServiceException(Exception):
    def __init__(self, message: str):
        super().__init__(message)

class InvalidMessageFormatException(ChatServiceException):
    def __init__(self, message: str):
        super().__init__(message)

class MessageReceiveException(ChatServiceException):
    def __init__(self, message: str):
        super().__init__(message)

class MessagePublishException(ChatServiceException):
    def __init__(self, message: str):
        super().__init__(message)

class WebSocketException(ChatServiceException):
    def __init__(self, message: str):
        super().__init__(message)