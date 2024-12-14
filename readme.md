If you’re reading this document, you’ve been directed to take over the paper evaluation and scoring project. The code for the project is in the paper-eval branch of the `bsn-server` repository, and is in the file `equality.py`. Test files for use in evaluation are in the same branch, just listed as `AC20-*.ifc` (there should be 4 of them). If you have your development environment set up properly, you should be able to run the evaluation code by typing in the following commands in your terminal session in the bsn-server folder (along with the current output for the commands):
```
bsn-server % python3
# Python REPL startup code
>>> import equality # Load in the evaluator
>>> model = equality.IfcEquality() # Initialize the evaluator
>>> model.file_equals("AC20-FZK-Haus_Test.ifc", "AC20-FZK-Haus_Original.ifc") # Feed the evaluator with the first two files
Score for the files (<ifcopenshell.file.file object at 0x10744dbd0> and <ifcopenshell.file.file object at 0x106f27690>): 0.2432432432432432
 Total number of elements: 88
 Number of elements that could not be successfully compared: 51
>>> model.file_equals("AC20-Institute-Var-2_Original.ifc", "AC20-Institute-Var-2_Test.ifc") # Second set
Score for the files (<ifcopenshell.file.file object at 0x10744dbd0> and <ifcopenshell.file.file object at 0x106f26b90>): 0.24795531617793665
 Total number of elements: 1196
 Number of elements that could not be successfully compared: 639
```
Note: running the evaluator will take a while (like 15 minutes for both, do something else while waiting) due to a lack of time to actually optimize this iteration of the code. You have two paths for fixing the evaluation code, as far as I can tell (located in the class `IfcEquality` in `equality`): a. argue for a swap back from the existing points scoring system for elements to a binary evaluator, or b. Reimplement the scoring algorithm for elements without a perfect match such that the algorithm picks the most optimal set of scores between the two sets of elements. 
In regard to matter a you can use the existing product_equals and file_equals functions that use a binary comparator stored under commit `57911c658f639d9dad45a8c3623741bd5ddff271` in `paper-eval`. Just make sure to change the get_material lines to get_materials or else material_equals will not function.

In regard to option b, your best bet is to change how you’re keeping track of the existing scores (probably to a flat dict that has a tuple of two `ifcopenshell.entity_instance`s (first_set, second_set) as the key and the score for them as a double), such that the scoring phase can flat for-loop through the scores dict (also, you may just want to remove the elements from their existing set, and loop through the existing dict, checking to see if the elements are in the first and second dicts, and only evaluating scoring if so). 

Also, as a closing note, don’t let AGGREGATE of Doubles get you down.