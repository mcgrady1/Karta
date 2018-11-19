from core.function_context import *
from config.utils          import *

class ExternalFunction(CodeContext) :
    """This class describes a source-code point of view of an external function, using references from/to it

    Attributes:
        hints (set): set of possible match (bin) candidates represented as eas
        xrefs (set): set of xrefs to this external function, as seen in the source project
    """
    def __init__(self, name) :
        """Basic Ctor for the class using only the name (ea is unknown untill we will have a match)

        Args:
            name (str): name of the external function
        """
        super(ExternalFunction, self).__init__(name)
        self.hints = None
        self.xrefs = set()

    # Overriden base function
    def declareMatch(self, match):
        self.match = match

    # Overriden base function
    def valid(self):
        return True

    def addXref(self, xref) :
        """Adds an xref to the function

        Args:
            xref (CodeContext): code context that calls (xrefs) our function
        """
        self.xrefs.add(xref)

    def removeXref(self, xref) :
        """Removes an xref from the function (the caller was probably found irrelevant for our search)

        Args:
            xref (CodeContext): code context that calls (xrefs) our function
        """
        if xref in self.xrefs :
            self.xrefs.remove(xref)

    def used(self) :
        """Checks if our external function is still used by active functions

        Return Value:
            True iff the function is used (has at least 1 active xref)
        """
        return len(self.xrefs) > 0

    def addHints(self, hints) :
        """Adds a collection of (bin) hints for our match

        Args:
            hints (collection): a collection of (bin) match hints, represented as eas
        """
        # filter out hints from known ignored libc functions
        if self.hints is None :
            self.hints = set(hints)
        else :
            self.hints = self.hints.intersection(hints)
        # check for a match
        if len(self.hints) == 1:
            self.declareMatch(list(self.hints)[0])

class ComparableContext(object) :
    """Base class representing the canonical representation of a function / code snippet, with the ability of being compared one to another

    Attributes:
        consts (set): set of numeric constants
        strings (set): set of string
        calls (set): set of (library) function calls (containing ComparableContext instances)
        externals (set): set of external function calls
        _const_ranks (dict): mapping from numeric const to it's score (calculated only once on start)
    """
    def __init__(self) :
        """Basic Ctor"""
        # artifacts
        self.consts       = set()
        self.strings      = set()
        # call references
        self.calls        = set()
        self.externals    = set()
        # preprocess results
        self._const_ranks = {}

    def recordConst(self, const) :
        """Records a numeric constant artifact in the code's artifacts list

        Args:
            const (int): numric constant artifact
        """
        self.consts.add(const)

    def recordString(self, string) :
        """Records a string artifact in the code's arteficts list

        Args:
            string (str): string artifact
        """
        self.strings.add(string)

    def recordCall(self, call) :
        """Records a function call artifact in the code's artifacts list

        Args:
            call (varies): name of ea that identifies the (basic) function call
        """
        self.calls.add(call)

    def rankConsts(self) :
        """Ranks all of the consts of our context - should be done only once on init"""
        for num_const in self.consts :
            self._const_ranks[num_const] = rankConst(num_const, self)

    @staticmethod
    def compareConsts(src_ctx, bin_ctx):
        """Compares the numerical constants of both contexts and returns the matching score

        Args:
            src_ctx (ComparableContext): context representing the source function
            bin_ctx (ComparableContext): context representing the binary function

        Return value
            floating point score for the constants comparison
        """
        score = 0
        # earn points by ranking the consts in the intersection
        for const in src_ctx.consts.intersection(bin_ctx.consts) :
            score += src_ctx._const_ranks[const]
        # deduce points by ranking the consts in the symmetric difference
        for const in src_ctx.consts.difference(bin_ctx.consts) :
            score -= src_ctx._const_ranks[const]
        for const in bin_ctx.consts.difference(src_ctx.consts) :
            score -= bin_ctx._const_ranks[const]
        # give a boost for a perfect match
        if len(src_ctx.consts) > 0 and src_ctx.consts == bin_ctx.consts :
            score += ARTIFACT_MATCH_SCORE
        return score

    @staticmethod
    def compareString(src_ctx, bin_ctx):
        """Compares the strings of both contexts and returns the matching score

        Args:
            src_ctx (ComparableContext): context representing the source function
            bin_ctx (ComparableContext): context representing the binary function

        Return value
            floating point score for the strings comparison
        """
        score = 0
        # start with a bonus score in case the string is contained in the source function's name
        try:
            score += STRING_NAME_SCORE * len(filter(lambda s : s in src_ctx.name, bin_ctx.strings))
        except UnicodeDecodeError, e:
            pass
        # now actually match the strings (intersection and symmetric difference)
        for string in src_ctx.strings.intersection(bin_ctx.strings) :
            score += len(string) * STRING_MATCH_SCORE
            # duplicate the bonus in this case
            if string in src_ctx.name :
                score += STRING_NAME_SCORE
        # deduce points for strings in the symmetric difference
        for string in src_ctx.strings.symmetric_difference(bin_ctx.strings) :
            score -= len(string) * STRING_MISMATCH_SCORE
        # give a boost for a perfect match
        if len(src_ctx.strings) > 0 and src_ctx.strings == bin_ctx.strings :
            score += ARTIFACT_MATCH_SCORE
        return score

    @staticmethod
    def compareCalls(src_ctx, bin_ctx):
        """Compares the function calls of both contexts and returns the matching score

        Args:
            src_ctx (ComparableContext): context representing the source function
            bin_ctx (ComparableContext): context representing the binary function

        Return value
            floating point score for the calls comparison
        """
        score = -1 * abs(len(src_ctx.calls) - len(bin_ctx.calls)) * CALL_COUNT_SCORE
        # penalty for missing matched calls
        src_matched = filter(lambda x : x.matched(), src_ctx.calls)
        bin_matched = filter(lambda x : x.matched(), bin_ctx.calls)
        mismatching  = []
        mismatching += filter(lambda x : x.match not in bin_ctx.calls, src_matched)
        mismatching += filter(lambda x : x.match not in src_ctx.calls, bin_matched)
        matching = filter(lambda x : x.match in bin_ctx.calls, src_matched) 
        # the penalty is halved because we the list will most probably contain duplicates
        score -= CALL_COUNT_SCORE * len(mismatching) * 1.0 / 2
        score += MATCHED_CALL_SCORE * len(matching)
        # give a boost for a perfect match
        if len(mismatching) == 0 and len(src_ctx.calls) > 0 and len(src_ctx.calls) == len(bin_ctx.calls) :
            score += ARTIFACT_MATCH_SCORE
        return score

    @staticmethod
    def compareExternals(src_ctx, bin_ctx):
        """Compares the (matched) external function calls of both contexts and returns the matching score

        Args:
            src_ctx (ComparableContext): context representing the source function
            bin_ctx (ComparableContext): context representing the binary function

        Return value
            floating point score for the external calls comparison
        """
        # penalty for number of missing external calls
        score = -1 * abs(len(src_ctx.externals) - len(bin_ctx.externals)) * EXTERNAL_COUNT_SCORE
        for external in filter(lambda x : x.matched(), src_ctx.externals) :
            # check for a hit
            if external.match in bin_ctx.externals :
                if external.name in libc.libc_function_names :
                    score += LIBC_COMP_FUNC_MATCH_SCORE if external.name in libc.libc_comp_function_names else LIBC_FUNC_MATCH_SCORE
                else :
                    score += EXT_FUNC_MATCH_SCORE
        # give a boost for a perfect match
        if len(src_ctx.externals) > 0 and len(src_ctx.externals) == len(bin_ctx.externals) :
            score += ARTIFACT_MATCH_SCORE
        return score

# Technically, BinaryCodeContext is mapped (has an index), and Island don't have an index.
# However this is much easier to implement instead of having a diamond shaped inheritance...
class IslandContext(BinaryCodeContext, ComparableContext) :
    """This class describes the canonical representation of a (bin) "Island" function that lives inside another binary function

    Attributes:
        xrefs (set): set of (library) function xrefs (containing ComparableContext instances)
    """
    def __init__(self, name, ea) :
        BinaryCodeContext.__init__(self, name, ea, None)
        ComparableContext.__init__(self)
        self.xrefs = set()

    # Overriden base function
    def isPartial(self) :
        return True

    # Overriden base function
    def valid(self) :
        return True

    # Overriden base function
    def preprocess(self):
        self.rankConsts()

    def compare(self, src_ctx, logger) :
        """Compares our island to a potential source match

        Args:
            src_ctx (SourceContext): src context representing a source function (potential match)
            logger (logger): logger instance

        Return Value:
            floating point score for the entire match
        """
        score = 0
        logger.addIndent()
        boost_score = len(src_ctx.blocks) <= MINIMAL_BLOCKS_BOOST
        # 1. Match constants
        const_score = ComparableContext.compareConsts(src_ctx, self)
        logger.debug("Const score: %f", const_score)
        score += const_score
        # 2. Match strings
        string_score = ComparableContext.compareString(src_ctx, self)
        logger.debug("String score: %f", string_score)
        score += string_score
        # 3. Match calls
        calls_score = ComparableContext.compareCalls(src_ctx, self)
        logger.debug("Calls score: %f", calls_score)
        score += calls_score
        # 4. Match external calls
        externals_score = ComparableContext.compareExternals(src_ctx, self)
        logger.debug("Externals score: %f", externals_score)
        score += externals_score
        # 5. Boost the score
        if boost_score :
            score *= 2
            logger.debug("Score boost")
        # Overall result
        logger.debug("Overall score is: %f", score)
        logger.removeIndent()
        return score

class FunctionContext(ComparableContext) :
    """Base class representing the full canonical representation of a function

    Attributes:
        xrefs (set): set of (library) function xrefs (containing ComparableContext instances)
        frame (int): size (in bytes) of the function's stack frame
        instrs (int): number of code instruction in our function
        blocks (list): (sorted) list containing the number of instructions in each code block
        call_order (dict): a mapping of: call invocation => set of call invocations that can reach it
        is_static (bool): True iff the function is not exported outside of it's local compiled file
    """
    def __init__(self) :
        """Basic Ctor"""
        super(FunctionContext, self).__init__()
        # artifacts
        self.xrefs      = set()
        self.frame      = None
        self.instrs     = None
        self.blocks     = []
        self.call_order = None
        # is static
        self.is_static  = False # False by default

    def setFrame(self, frame) :
        """Sets the size of the stack frame for our function

        Args:
            frame (int): frame size (in bytes) of our function
        """
        self.frame = frame

    def setInstrCount(self, num_instrs) :
        """Sets the number of code instructionsin our function

        Args:
            num_instrs (int): number of instructions in the function
        """
        self.instrs = num_instrs

    def recordBlock(self, block) :
        """Records a code block in our function's code flow

        Args:
            block (int): number of instructions in the given code block
        """
        self.blocks.append(block)

    def setCallOrder(self, mapping) :
        """Sets the call order mapping: call invocation => set of call invocations that can reach it

        Args:
            mapping (dict): mapping of the call order
        """
        self.call_order = mapping

    def markStatic(self) :
        """Marks our source function as a non-exported (static) function"""
        self.is_static = True

    def used(self) :
        """Check if our function is used, i.e. has ingoing/outgoing reference to other functions

        Return value:
            True iff the function has any call/xref to other functions
        """
        return len(self.calls) + len(self.xrefs) > 0

class SourceContext(SrcFileFunction, FunctionContext):
    """This class describes the canonical representation of a source file function, with it's full logic

    Attributes:
        unknown_funcs (set): temporary set of (source) function names from outside of our compilation file
        unknown_fptrs (set): temporary set of (source) function (pointer) names from outside of our compilation file
        hash (str): hex digest of the function's hash (calculated on the raw binary)
        call_order (dict): a mapping of: call invocation => set of call invocations that can reach it
        followers (set): set of binary functions that use us as a potential match hint
        exists (bool): validity flag marking our existence in the source (according to info from the binary match)
        file_hint (str): source file name string if exists inside function, None otherwise
        collision_candidates (list) : list of src candidates with a possibility for merging (same name + linker optimizations)
    """

    def __init__(self, name, index) :
        """Basic Ctor for the class

        Args:
            name (str): source function name
            index (int): index of the function in the global array of all source functions
        """
        SrcFileFunction.__init__(self, name, index)
        FunctionContext.__init__(self)
        # temporary field
        self.unknown_funcs = set()
        self.unknown_fptrs = set()
        # artifacts
        self.hash       = None
        # matching hints
        self.followers  = set()
        # validity flag
        self.exists     = True
        # File (source) hint
        self.file_hint  = None
        # Compilation clues
        self.is_static  = False
        # Linker optimizations
        self.collision_candidates = []

    # Overriden base function
    def declareMatch(self, match):
        self.match = match
        # notify our followers that we are now out of the game
        for follower in self.followers :
            follower.removeHint(self, clear = False)
        self.followers = set()

    # Overriden base function
    def isPartial(self) :
        return False

    # Overriden base function
    def valid(self):
        return self.exists

    # Overriden base function
    def preprocess(self):
        self.rankConsts()

    # Overriden base function
    def disable(self) :
        """Marks our source function as non-existant (probably ifdeffed out)"""
        # singleton lock
        if not self.exists :
            return
        # can now safely continue
        self.exists = False
        # keep on recursively with our external functions
        for ext in self.externals :
            ext.removeXref(self)
        # mark that I'm no longer a valid collision candidate
        for collision_candidate in self.collision_candidates :
            collision_candidate.collision_candidates.remove(self)
        self.collision_candidates = []

    def recordUnknown(self, unknown, is_fptr = False) :
        """Records a function call to an unknown function

        Args:
            unknown (str): name of an unknown source function
            is_fptr (bool): True if this is an unknown fptr (False by default)
        """
        if not is_fptr:
            self.unknown_funcs.add(unknown)
        else:
            self.unknown_fptrs.add(unknown)

    def setHash(self, digest) :
        """Sets the hash digest of our function

        Args:
            digest (str): hex digest of our function
        """
        self.hash = digest

    def markCollisionCandidates(self, candidates):
        """Marks the potential collision (merge) candidates from other files

        Args:
            candidates (list): list of src context candidates
        """
        self.collision_candidates = [] + candidates
        # no need to count me in
        self.collision_candidates.remove(self)

    def addFollower(self, bin_ctx) :
        """Adds a binary follower to our source context. He thinks we are a potential (hint) match

        Args:
            bin_ctx (ComparableContext): binary function that follows us using a hint
        """
        self.followers.add(bin_ctx)

    def removeFollower(self, bin_ctx) :
        """Removes a (binary) follower from our watch list (he was probably matched without us)

        Args:
            bin_ctx (ComparableContext): a follower (binary) function
        """
        if bin_ctx in self.followers :
            self.followers.remove(bin_ctx)

    def checkFileHint(self) :
        """After all strings were recorded, checks if has a file string hint
        
        Return Value :
            source file name string hint iff found one, None otherwise
        """
        for string in self.strings :
            name_parts = string.split('.')
            if len(name_parts) != 2 :
                continue
            file_name = self.file.split(os.path.sep)[-1].split('.')[0]
            if name_parts[0] == file_name and name_parts[1].lower() in ['c', 'cpp', 'c++'] :
                self.file_hint = string
                return self.file_hint
        return None

    def isValidCandidate(self, bin_ctx) :
        """Check if the given binary context is a valid match candidate

        Args:
            bin_ctx (ComparableContext): context representing a binary function (potential match)
        
        Return Value:
            False iff the binary context was found as an invalid match candidate
        """
        # 0. Both must be in the game
        if not self.active() or not bin_ctx.active() :
            return False

        # 1. They must be in the same file
        if not bin_ctx.isFileSuitable(self) :
            return False

        # 2. A static function can not have an xref from outside the library (weak because of possible inlining)
        if self.is_static and not bin_ctx.is_static :
            return False

        # If reached this line, the candidate is probably fine
        return True

    def compare(self, bin_ctx, logger) :
        """Compares our (source) function to a potential binary match

        Args:
            bin_ctx (ComparableContext): context representing a binary function (potential match)
            logger (logger): logger instance

        Return Value:
            floating point score for the entire match
        """
        score = 0
        logger.addIndent()
        # 0. prepare the instruction ratio (if has one already)
        instr_ratio = (src_instr_count * 1.0 / bin_instr_count) if num_instr_samples >= INSTR_RATIO_COUNT_THRESHOLD else 1
        boost_score = len(self.blocks) <= MINIMAL_BLOCKS_BOOST and len(bin_ctx.blocks) <= MINIMAL_BLOCKS_BOOST
        boost_score = boost_score and bin_ctx.call_hints is None and len(bin_ctx.xref_hints) == 0
        # 1. Match constants
        const_score = ComparableContext.compareConsts(self, bin_ctx)
        logger.debug("Const score: %f", const_score)
        score += const_score
        # 2. Match strings
        string_score = ComparableContext.compareString(self, bin_ctx)
        logger.debug("String score: %f", string_score)
        score += string_score
        # 3. Match sizes
        function_size_score = -1 * abs(self.instrs - bin_ctx.instrs * instr_ratio) * INSTR_COUNT_SCORE
        # check for a probable match
        if abs(function_size_score) <= INSTR_COUNT_THRESHOLD * INSTR_COUNT_SCORE :
            function_size_score += ARTIFACT_MATCH_SCORE
        logger.debug("Function size score: %f", function_size_score)
        score += function_size_score
        # 4. Match stack frames
        frame_size_score = -1 * abs(self.frame - bin_ctx.frame) * FUNC_FRAME_SCORE
        # check for a probable match
        if abs(frame_size_score) <= FRAME_SIZE_THRESHOLD * FUNC_FRAME_SCORE :
            frame_size_score += ARTIFACT_MATCH_SCORE
        logger.debug("Frame size score: %f", frame_size_score)
        score += frame_size_score
        # 5. Match calls
        calls_score = ComparableContext.compareCalls(self, bin_ctx)
        logger.debug("Calls score: %f", calls_score)
        score += calls_score
        # 6. Match code blocks
        code_blocks_score = 0
        for index, block in enumerate(self.blocks) :
            code_blocks_score -= abs(self.blocks[index] - ((bin_ctx.blocks[index] * instr_ratio) if index < len(bin_ctx.blocks) else 0)) * BLOCK_MATCH_SCORE
        for j in xrange(index + 1, len(bin_ctx.blocks)) :
            code_blocks_score -= bin_ctx.blocks[j] * BLOCK_MISMATCH_SCORE * instr_ratio
        # check for a probable match
        if abs(code_blocks_score) <= INSTR_COUNT_THRESHOLD * INSTR_COUNT_SCORE :
            code_blocks_score += ARTIFACT_MATCH_SCORE
        logger.debug("Code blocks score: %f", code_blocks_score)
        score += code_blocks_score
        # 7. Match function calls (hints)
        call_hints_score = 0
        merged_hints = 0
        if bin_ctx.call_hints is not None and len(bin_ctx.call_hints) > 0 and self in bin_ctx.call_hints :
            merged_hints = len(filter(lambda x : x.hash == self.hash, bin_ctx.call_hints))
            # prioritize merged hints
            call_hints_score += FUNC_HINT_SCORE * 1.0 * (merged_hints ** 1.5) / len(bin_ctx.call_hints)
        logger.debug("Call hints score: %f", call_hints_score)
        score += call_hints_score
        # 8. Match xrefs calls (hints)
        if len(bin_ctx.xref_hints) > 0 :
            xref_hints_score = FUNC_HINT_SCORE * bin_ctx.xref_hints.count(self) * 1.0 / len(bin_ctx.xref_hints)
            logger.debug("Xref hints score: %f", xref_hints_score)
            score += xref_hints_score
        # 9. Existence check (followers) or non static binary function
        if len(self.followers) > 0 or not bin_ctx.is_static :
            logger.debug("We have (%d) followers / are static (%s) - grant an existence bonus: %f", len(self.followers), str(bin_ctx.is_static), EXISTENCE_BOOST_SCORE)
            score += EXISTENCE_BOOST_SCORE
        # 10. Match external calls
        externals_score = ComparableContext.compareExternals(self, bin_ctx)
        logger.debug("Externals score: %f", externals_score)
        score += externals_score
        # 11. Possible static deduction (if no probability for a collision)
        if self.is_static and merged_hints == 0 :
            static_penalty = 0
            for xref in bin_ctx.xrefs :
                if self.file not in xref.files :
                    static_penalty += STATIC_VIOLATION_PENALTY
            logger.debug("Static penalty score: %f", static_penalty)
            score -= static_penalty
        # 12. Score boost
        if boost_score :
            score *= 2
            logger.debug("Score boost")
        # Overall result
        logger.debug("Overall score is: %f", score)
        logger.removeIndent()
        return score

    def serialize(self) :
        """Serializes the context into a dict

        Return Value:
            dict representing the context instance, prepared for a future JSON dump
        """
        result = collections.OrderedDict()
        result['Function Name']     = self.name
        result['Instruction Count'] = self.instrs
        result['Stack Frame Size']  = self.frame
        result['Hash']              = self.hash
        result['Is Static']         = self.is_static
        result['Numeric Consts']    = list(self.consts)
        result['Strings']           = list(self.strings)
        result['Calls']             = list(self.calls)
        result['Unknown Functions'] = list(self.unknown_funcs)
        result['Unknown Globals']   = list(self.unknown_fptrs)
        result['Code Block Sizes']  = self.blocks
        result['Call Order']        = self.call_order
        return result

    @staticmethod
    def deserialize(serialized_ctx, source_index) :
        """Deserializes the stored context from it's file representation dict

        Args:
            serialized_ctx (dict): a dict containg a serialize()d context instance
            source_index (int): source index for the current function

        Return value:
            The newly created context instance, built according to the serialized form
        """
        context = SourceContext(serialized_ctx['Function Name'], source_index)
        # Numeric Consts
        map(lambda x : context.recordConst(x), serialized_ctx['Numeric Consts'])
        # Strings
        map(lambda x : context.recordString(x), serialized_ctx['Strings'])
        # Function Calls
        map(lambda x : context.recordCall(x), serialized_ctx['Calls'])
        # Unknowns
        map(lambda x : context.recordUnknown(x, False), serialized_ctx['Unknown Functions'])
        map(lambda x : context.recordUnknown(x, True), serialized_ctx['Unknown Globals'])
        # Hash
        context.setHash(serialized_ctx['Hash'])
        # Frame size
        context.setFrame(serialized_ctx['Stack Frame Size'])
        # Function size
        context.setInstrCount(serialized_ctx['Instruction Count'])
        # Function Blocks
        map(lambda x : context.recordBlock(x), serialized_ctx['Code Block Sizes'])
        # Call order
        context.setCallOrder(serialized_ctx['Call Order'])
        # Is static
        if serialized_ctx['Is Static'] :
            context.markStatic()
        # Now rank the consts
        context.rankConsts()
        return context

class BinaryContext(BinFileFunction, FunctionContext):
    """This class describes the full canonical representation of a binary function, with all of it's logic

    Attributes:
        call_hints (set): set of potential matches derived by lists of function calls from matched functions
        xref_hints (list): list potential matches derived by lists of xrefs from matched functions
        collision_map (dict): a mapping of seen collision options: hint id ==> list of possible (seen) collisions
        taken_collision (bool): True iff was merged as part of a collision
        merged_sources (list): list of merged source functions (in a collision case)
    """

    def __init__(self, ea, name, index) :
        """Basic Ctor for the class

        Args:
            ea (int): effective address of the given code chunk
            name (str): temporary (?) name given by the disassembler
            index (int): index of the function in the global array of all binary functions
        """
        BinFileFunction.__init__(self, ea, name, index)
        FunctionContext.__init__(self)
        # matching hints
        self.call_hints = None
        self.xref_hints = []
        # validity flag
        self.exists     = True
        # Compilation clues
        self.is_static  = False
        # Linker optimizations
        self.collision_map      = {}
        self.taken_collision    = False
        self.merged_sources     = []

    # Overriden base function
    def declareMatch(self, match):
        self.match = match
        # notify our hints that we are out of the game
        if self.call_hints is not None :
            for hint in list(self.call_hints) :
                self.removeHint(hint, clear = True)
        for hint in list(self.xref_hints) :
            self.removeHint(hint, clear = True)
        # If we chose a collision candidate, when we saw the possibility for a collision, it means it is indeed an active collision
        if match.hash in self.collision_map or (len(self.files) > 0 and match.file not in self.files) :
            self.merged_sources.append(match)
            self.taken_collision = True
            # make sure that our match will always be in our map
            if match.hash not in self.collision_map:
                self.collision_map[match.hash] = []

    # Overriden base function
    def isPartial(self) :
        return False

    # Overriden base function
    def valid(self):
        return self.exists

    # Overriden base function
    def preprocess(self):
        self.rankConsts()

    # Overriden base function
    def active(self) :
        # special case for collisions
        return self.valid() and (self.mergePotential() or not self.matched())

    # Overriden base function
    def selfCheck(self):
        """Double checks our hints, and keeps only those who match our possible file candidates"""
        for hint in set(self.xref_hints).union(self.call_hints if self.call_hints is not None else set()) :
            # bye bye, hint
            if not hint.isValidCandidate(self) :
                self.removeHint(hint)

    # Overriden base function
    def isLinkerOptimizationCandidate(self, src_ctx):
        # edge case for possibile collision candidates
        # 1. Matched to one candidate, and checking to merge more src functions
        if self.merged() and self.match in src_ctx.collision_candidates :
            return True
        # 2. Didn't match yet, however one collision candidate is a valid candidate
        for collision in src_ctx.collision_candidates :
            if collision.file in self.files :
                return True
        # If we reached this point, it looks like they don't belong to each other
        return False

    def merged(self):
        """Checks if this is a merged (collision) function

        Return value:
            True iff this is a merged function
        """
        return self.taken_collision

    def mergePotential(self):
        """Checks if this is a collision function with a potential to merge more src functions

        Return value:
            True iff this is a merged function with growth potential
        """
        return self.matched() and (not self.match.isPartial()) and len(filter(lambda x : not x.matched(), self.match.collision_candidates)) > 0

    def isHinted(self) :
        """ Check if our function was hinted at sometimes - meaning we should suspect it is a valid function

        Return value:
            True iff the function has any call/xref hint granted by other functions
        """
        return (self.call_hints is not None and len(self.call_hints) > 0) or len(self.xref_hints) > 0        

    def addHints(self, hints, is_call) :
        """Adds a set of (source) match hints to help us filter our existing hints

        Args:
            hint (collection): a collection of (source) function potential matches (containing FunctionContext instances)
            is_call (bool): True iff call hints, otherwise xref hints
        """
        new_hints = filter(lambda x : x.isValidCandidate(self), hints)

        # Saw a collision candidate, after was already matched to one of his friends
        if self.matched() :
            # Only candidate hints can reach this point, and they all should be matched
            # Later on, the matching round will declare them as matched
            if len(new_hints) > 0 :
                self.call_hints = new_hints
                if new_hints[0].hash not in self.collision_map :
                    self.collision_map[new_hints[0].hash] = set()
                self.collision_map[new_hints[0].hash].update(new_hints)
            return

        # normal case
        if is_call :
            if self.call_hints is None :
                self.call_hints = set(new_hints)
                for hint in new_hints :
                    hint.addFollower(self)
            else :
                # linker optimizations edge case
                new_hashes = map(lambda x: x.hash, new_hints)
                cur_hashes = map(lambda x: x.hash, self.call_hints)
                for dropped in filter(lambda x: x.hash not in new_hashes, self.call_hints):
                    dropped.removeFollower(self)
                # check for a possibile collision option
                context_intersection = self.call_hints.intersection(new_hints)
                context_union        = self.call_hints.union(new_hints)
                hashes_intersection  = set(cur_hashes).intersection(new_hashes)
                remaining_hashes     = map(lambda x : x.hash, context_intersection)
                if len(hashes_intersection) > len(remaining_hashes) :
                    collision_candidates = []
                    for collision_hash in set(hashes_intersection).difference(remaining_hashes) :
                        if collision_hash not in self.collision_map:
                            self.collision_map[collision_hash] = set()
                        cur_collision_candidates = filter(lambda x : x.hash == collision_hash, context_union)
                        self.collision_map[collision_hash].update(cur_collision_candidates)
                        collision_candidates += cur_collision_candidates
                    self.call_hints = context_intersection.union(collision_candidates)
                else :
                    self.call_hints = self.call_hints.intersection(new_hints)
        else :
            self.xref_hints += new_hints
            for hint in new_hints :
                hint.addFollower(self)

    def removeHint(self, src_ctx, clear = True) :
        """Removes a (source) hint from our possible candidates (he was probably matched without us)

        Args:
            src_ctx (FunctionContext): a hint (source) function
            clear (bool, optional): True iff should also remove us from following him (True by default)
        """
        if clear :
            src_ctx.removeFollower(self)
        if self.call_hints is not None :
            while src_ctx in self.call_hints :
                self.call_hints.remove(src_ctx)
        while src_ctx in self.xref_hints :
            self.xref_hints.remove(src_ctx)