// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a global predictor. 
//
// How it works (see the Pentium M diagram in the assignment handout):
//
//   Bimodal table      4096 two-bit counters indexed by IP[11:0].  This is the
//                      "local" predictor that every branch falls back on.
//
//   Global predictor   512 sets x 4 ways.  Each entry holds a valid bit, a 6-bit
//                      tag and a two-bit counter.  Set index and tag come from a
//                      15-bit hash of the branch address and the global history:
//                          hash  = IP[14:0] xor GHR[14:0]
//                          index = hash[14:6]   (9 bits -> 512 sets)
//                          tag   = hash[5:0]    (6 bits)
//                      The real Pentium M hashes the IP with a path information
//                      register (PIR).  The handout says the PIR is not required,
//                      so a plain global history register (GHR) holding the last
//                      15 branch outcomes is used instead, like in gshare above.
//
//   Final prediction   If the tag is found in one of the ways ("global hit") the
//                      global counter decides, otherwise the bimodal counter does.
//
//   Update             Both tables are trained after every conditional branch.
//                      On a global miss the least recently used way of the set
//                      is given to the new tag.  The outcome is then shifted
//                      into the GHR.
//
class pm_update : public branch_update {
public:
	bool conditional;		// only conditional branches use and train the tables
	unsigned int bimodal_index;	// bimodal counter that was used
	unsigned int global_index;	// set of the global predictor that was searched
	unsigned int global_tag;	// tag that was searched for in that set
	int global_way;			// way that matched the tag, or -1 on a miss
};

class pm_predictor : public branch_predictor {
public:
	// sizes from the Pentium M diagram
	static const int BIMODAL_BITS = 12;			// 4096 counters, indexed by IP[11:0]
	static const int HASH_BITS    = 15;			// hash = IP[14:0] xor GHR[14:0]
	static const int TAG_BITS     = 6;			// tag = hash[5:0]
	static const int INDEX_BITS   = HASH_BITS - TAG_BITS;	// index = hash[14:6], 512 sets
	static const int WAYS         = 4;			// 4-way set associative

	static const int BIMODAL_SIZE = 1 << BIMODAL_BITS;
	static const int SETS         = 1 << INDEX_BITS;

	// one way of one set of the global predictor
	struct global_entry {
		bool valid;
		unsigned int tag;
		unsigned char counter;	// two-bit saturating counter, 2 or 3 means taken
		unsigned char lru;	// 0 = most recently used ... WAYS-1 = least recently used
	};

	pm_update u;
	unsigned char bimodal[BIMODAL_SIZE];	// two-bit saturating counters
	global_entry global[SETS][WAYS];
	unsigned int history;			// global history register (GHR)

	pm_predictor (void) : history(0) {
		memset (bimodal, 0, sizeof (bimodal));
		for (int s = 0; s < SETS; s++) {
			for (int w = 0; w < WAYS; w++) {
				global[s][w].valid = false;
				global[s][w].tag = 0;
				global[s][w].counter = 0;
				// way 0 starts out as least recently used, so it is filled first
				global[s][w].lru = WAYS - 1 - w;
			}
		}
	}

	// two-bit saturating counter: count up when taken, down when not taken
	static void train (unsigned char & counter, bool taken) {
		if (taken) {
			if (counter < 3) counter++;
		} else {
			if (counter > 0) counter--;
		}
	}

	// look for a tag in a set; returns the way that holds it, or -1 if none does
	int find_way (unsigned int index, unsigned int tag) {
		for (int w = 0; w < WAYS; w++) {
			if (global[index][w].valid && global[index][w].tag == tag) return w;
		}
		return -1;
	}

	// the way that has gone unused the longest; it is the one replaced on a miss
	int lru_way (unsigned int index) {
		for (int w = 0; w < WAYS; w++) {
			if (global[index][w].lru == WAYS - 1) return w;
		}
		return 0;	// never reached: the lru values of a set are always 0..WAYS-1
	}

	// make a way the most recently used one and age the others in the set
	void touch (unsigned int index, int way) {
		unsigned char old_lru = global[index][way].lru;
		for (int w = 0; w < WAYS; w++) {
			if (global[index][w].lru < old_lru) global[index][w].lru++;
		}
		global[index][way].lru = 0;
	}

	branch_update *predict (branch_info & b) {
		u.conditional = (b.br_flags & BR_CONDITIONAL) != 0;

		if (u.conditional) {
			// bimodal lookup
			u.bimodal_index = b.address & (BIMODAL_SIZE - 1);
			bool bimodal_taken = bimodal[u.bimodal_index] >= 2;

			// global lookup
			unsigned int hash = (b.address ^ history) & ((1 << HASH_BITS) - 1);
			u.global_index = hash >> TAG_BITS;
			u.global_tag = hash & ((1 << TAG_BITS) - 1);
			u.global_way = find_way (u.global_index, u.global_tag);

			// the global predictor wins when it has a matching entry,
			// otherwise the bimodal predictor is used
			if (u.global_way >= 0) {
				u.direction_prediction (global[u.global_index][u.global_way].counter >= 2);
			} else {
				u.direction_prediction (bimodal_taken);
			}
		} else {
			// unconditional branches, calls and returns are always taken
			// (the driver does not count them anyway)
			u.direction_prediction (true);
		}

		// branch target prediction is not part of this assignment
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *bu, bool taken, unsigned int target) {
		pm_update *pu = (pm_update *) bu;
		if (!pu->conditional) return;

		// 1. train the bimodal counter
		train (bimodal[pu->bimodal_index], taken);

		// 2. train the global predictor.  On a miss the least recently used
		//    way of the set is handed to this branch's tag and its counter is
		//    then trained like on a hit, as in the worked example of the handout.
		int way = pu->global_way;
		if (way < 0) {
			way = lru_way (pu->global_index);
			global[pu->global_index][way].valid = true;
			global[pu->global_index][way].tag = pu->global_tag;
		}
		train (global[pu->global_index][way].counter, taken);
		touch (pu->global_index, way);

		// 3. shift the outcome into the global history register
		history = ((history << 1) | taken) & ((1 << HASH_BITS) - 1);
	}

};

//
// Complete Pentium M branch predictors for extra credit
// This class implements the complete Pentium M branch prediction units. 
// It implements both branch target prediction and branch outcome predicton. 
class cpm_update : public branch_update {
public:
        unsigned int index;
};

class cpm_predictor : public branch_predictor {
public:
        cpm_update u;

        cpm_predictor (void) {
        }

        branch_update *predict (branch_info & b) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *u, bool taken, unsigned int target) {
        }

};


