# Independent contract annotation packet

Six previously unexposed task-family descriptions from a pinned Reasoning Gym snapshot. These are question templates with named instance placeholders, not concrete generated samples. Do not solve the placeholders. There is no scorer, answer key, issue/repair status or model output here.

For each task, independently state: (1) answer meaning; (2) necessary conditions for full credit; (3) explicit output format; (4) normalization explicitly permitted by the wording; (5) what remains unspecified (including partial rewards). Do not infer an implementation policy that the question does not state.

## T01

Two strings are isomorphic if the characters in one string can be replaced to get the second string.

All occurrences of a character must be replaced with another character while preserving the order of characters.

No two characters may map to the same character, but a character may map to itself.

Return True if the following two strings are isomorphic, or False otherwise:
{s} {t}


Placeholder notes: {"s": "instance-specific first string", "t": "instance-specific second string"}

Your contract:

## T02

Given two strings representing a ransom note and a magazine, return True if you can construct the ransom note using the letters in the magazine, and False otherwise.

Each letter in the magazine string can only be used once in your ransom note.

Ransom note: {ransom_note}
Magazine: {magazine}


Placeholder notes: {"ransom_note": "instance-specific ransom-note string", "magazine": "instance-specific available-letter string"}

Your contract:

## T03

There are a total of {num_courses} courses you have to take, labeled from 0 to {last_index}.

You are given the following list of prerequisites, where prerequisites[i] = (a_i, b_i) indicates that you must first take course b_i if you want to take course a_i:
{prerequisites}

Return True if you can finish all courses considering the prerequisites, or False otherwise.


Placeholder notes: {"num_courses": "instance-specific total number of courses", "last_index": "num_courses - 1", "prerequisites": "instance-specific list of course-index prerequisite pairs"}

Your contract:

## T04

Count how many prime numbers there are between {start} and {end} (inclusive) ?

Placeholder notes: {"start": "instance-specific interval start integer", "end": "instance-specific interval end integer, not below start"}

Your contract:

## T05

Sort these numbers in {direction} order: {numbers}
Please follow the instruction below:
## 1. Let all your answers be a list of numbers. Instead of reporting your answer as -69, -13, 1, 7, 11, 43, 59, 61, use ['-69', '-13', '1', '7', '11', '43', '59', '61'] instead
## 2. Convert all numbers in the square brackets as strings. For example, ['-69', '-13', '1', '7', '11', '43', '59', '61']


Placeholder notes: {"direction": "instance-specific 'ascending' or 'descending'", "numbers": "instance-specific comma-separated input numbers"}

Your contract:

## T06

Simplify the fraction {question_fraction} to its lowest terms. Give only the simplified fraction as your final answer.

Placeholder notes: {"question_fraction": "instance-specific input fraction in its displayed representation"}

Your contract:

