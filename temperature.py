def count_above_threshold(numbers, threshold):
    count = 0
    for number in numbers:
        if number is None:
            continue
        if number > threshold:
            count += 1

    return  count