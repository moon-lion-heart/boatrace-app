class Colorize:
    @staticmethod
    def royal_blue(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;65;105;225m{text:<{allocated_size}}\033[0m"
	
    @staticmethod
    def teal(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;0;128;128m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def medium_aqua_marine(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;102;205;170m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def aqua_marine(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;127;255;212m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def lime(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;0;255;0m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def salmon(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;250;128;114m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def red(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;255;0;0m{text:<{allocated_size}}\033[0m"

    @staticmethod
    def deep_pink(text, allocated_size=None):
        if allocated_size is None: allocated_size = len(text)
        return f"\033[38;2;255;20;147m{text:<{allocated_size}}\033[0m"