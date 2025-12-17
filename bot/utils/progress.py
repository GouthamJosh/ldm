def progress_bar(done, total):
    if total == 0:
        return "░" * 20
    filled = int((done / total) * 20)
    return "█" * filled + "░" * (20 - filled)
