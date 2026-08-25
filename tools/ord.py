# -*- coding: utf-8 -*-
"""The ordination engine: dissimilarity, PCoA, NMDS, Procrustes.

Kept out of the page for the same reason as the Field Entry Kit and the Darwin
Core exporter: an inlined copy that nothing regenerates drifts, and the
verification suite needs a source of truth to read a version and a term list
from rather than freezing one.

Everything here was checked against an independent implementation before it
shipped -- Bray-Curtis against scipy's, the PCoA eigenvalues against numpy's
symmetric solver, and the NMDS stress against scikit-learn's SMACOF, which is a
different algorithm reaching the same minimum. See tools/verify/verify_ord.py,
which redoes that comparison every run rather than trusting this comment.

    python3 tools/ord_emit.py           # rewrite the consumer
    python3 tools/ord_emit.py --check   # report drift, write nothing
"""
VERSION = "1.0.0"

JS = """
/* ---- Ordination v%s : NMDS (Kruskal 1964) and PCoA (Gower 1966) ---- */
var ORD = (function(){
  function zeros(n,m){ var A=[],i,j; for(i=0;i<n;i++){ A.push([]); for(j=0;j<m;j++) A[i].push(0);} return A; }

  /* ---- transforms ---- */
  function sqrtT(X){ return X.map(function(r){ return r.map(function(v){ return Math.sqrt(Math.max(0,v)); }); }); }
  /* vegan's wisconsin(): species by their maximum, then sites by their total. */
  function wisconsin(X){
    var n=X.length, m=X[0].length, i,j, Y=zeros(n,m);
    for(j=0;j<m;j++){ var mx=0; for(i=0;i<n;i++) mx=Math.max(mx,X[i][j]);
      if(mx===0) mx=1; for(i=0;i<n;i++) Y[i][j]=X[i][j]/mx; }
    for(i=0;i<n;i++){ var t=0; for(j=0;j<m;j++) t+=Y[i][j];
      if(t===0) t=1; for(j=0;j<m;j++) Y[i][j]=Y[i][j]/t; }
    return Y;
  }

  /* ---- dissimilarity ---- */
  function bray(X){
    var n=X.length, D=zeros(n,n), i,j,k;
    for(i=0;i<n;i++) for(j=i+1;j<n;j++){
      var num=0, den=0;
      for(k=0;k<X[i].length;k++){ num+=Math.abs(X[i][k]-X[j][k]); den+=X[i][k]+X[j][k]; }
      D[i][j]=D[j][i]= den===0 ? 0 : num/den;
    }
    return D;
  }
  function jaccard(X){
    var n=X.length, D=zeros(n,n), i,j,k;
    for(i=0;i<n;i++) for(j=i+1;j<n;j++){
      var a=0,b=0;
      for(k=0;k<X[i].length;k++){ var p=X[i][k]>0, q=X[j][k]>0;
        if(p&&q) a++; if(p||q) b++; }
      D[i][j]=D[j][i]= b===0 ? 0 : 1-a/b;
    }
    return D;
  }
  function euclid(X){
    var n=X.length, D=zeros(n,n), i,j,k;
    for(i=0;i<n;i++) for(j=i+1;j<n;j++){
      var s=0; for(k=0;k<X[i].length;k++){ var d=X[i][k]-X[j][k]; s+=d*d; }
      D[i][j]=D[j][i]=Math.sqrt(s);
    }
    return D;
  }

  /* ---- symmetric eigendecomposition, cyclic Jacobi ----
     Small n (sites, not species), so O(n^3) per sweep is free and Jacobi is
     the one algorithm short enough to read and check by hand. */
  function jacobi(Ain, maxSweep){
    var n=Ain.length, A=Ain.map(function(r){return r.slice();}), V=zeros(n,n), i,j,k,s;
    for(i=0;i<n;i++) V[i][i]=1;
    for(s=0;s<(maxSweep||100);s++){
      var off=0;
      for(i=0;i<n;i++) for(j=i+1;j<n;j++) off+=A[i][j]*A[i][j];
      if(off < 1e-22) break;
      for(i=0;i<n;i++) for(j=i+1;j<n;j++){
        if(Math.abs(A[i][j]) < 1e-18) continue;
        var theta=(A[j][j]-A[i][i])/(2*A[i][j]);
        var t=(theta>=0?1:-1)/(Math.abs(theta)+Math.sqrt(theta*theta+1));
        var c=1/Math.sqrt(t*t+1), sn=t*c;
        for(k=0;k<n;k++){
          var aik=A[i][k], ajk=A[j][k];
          A[i][k]=c*aik-sn*ajk; A[j][k]=sn*aik+c*ajk;
        }
        for(k=0;k<n;k++){
          var aki=A[k][i], akj=A[k][j];
          A[k][i]=c*aki-sn*akj; A[k][j]=sn*aki+c*akj;
          var vki=V[k][i], vkj=V[k][j];
          V[k][i]=c*vki-sn*vkj; V[k][j]=sn*vki+c*vkj;
        }
      }
    }
    var vals=[], idx=[];
    for(i=0;i<n;i++){ vals.push(A[i][i]); idx.push(i); }
    idx.sort(function(a,b){ return vals[b]-vals[a]; });
    return { values: idx.map(function(q){return vals[q];}),
             vectors: idx.map(function(q){ return V.map(function(row){ return row[q]; }); }) };
  }

  /* ---- PCoA (Gower 1966) ---- */
  function pcoa(D, k){
    var n=D.length, i, j;
    var A=zeros(n,n);
    for(i=0;i<n;i++) for(j=0;j<n;j++) A[i][j] = -0.5*D[i][j]*D[i][j];
    var rm=[], cm=[], gm=0;
    for(i=0;i<n;i++){ var s=0; for(j=0;j<n;j++) s+=A[i][j]; rm.push(s/n); gm+=s; }
    gm/=(n*n);
    for(j=0;j<n;j++){ var s2=0; for(i=0;i<n;i++) s2+=A[i][j]; cm.push(s2/n); }
    /* Double-centring, both terms. The column and grand-mean terms look
       redundant next to the row term, and for the EIGENVALUES they are --
       dropping them changes the spectrum by less than 1e-12 on any symmetric
       input, because what they remove is a rank-one component lying in the
       constant direction, which the spectrum never sees. The COORDINATES are
       another matter: on random dissimilarities, row-centring alone moves a
       point by as much as 2.5 units and breaks the identity that PCoA of a
       Euclidean distance matrix must reproduce that matrix exactly. Do not
       simplify this line; verify_ord.py checks the identity, not the
       eigenvalues, for exactly this reason. */
    var G=zeros(n,n);
    for(i=0;i<n;i++) for(j=0;j<n;j++) G[i][j]=A[i][j]-rm[i]-cm[j]+gm;
    var e=jacobi(G);
    var coords=zeros(n,k);
    for(var a=0;a<k;a++){
      var lam=Math.max(0, e.values[a]||0), sc=Math.sqrt(lam);
      for(i=0;i<n;i++) coords[i][a]=e.vectors[a][i]*sc;
    }
    var neg=0, posSum=0, absSum=0;
    e.values.forEach(function(v){ if(v < -1e-9) neg++; if(v>0) posSum+=v; absSum+=Math.abs(v); });
    return { coords:coords, values:e.values, negatives:neg, posSum:posSum, absSum:absSum };
  }

  /* ---- pool-adjacent-violators: isotonic regression on an ordered vector ---- */
  function pava(y){
    var n=y.length, v=[], w=[], i;
    for(i=0;i<n;i++){
      var vi=y[i], wi=1;
      while(v.length && v[v.length-1] > vi){
        var pv=v.pop(), pw=w.pop();
        vi = (pv*pw + vi*wi)/(pw+wi); wi = pw+wi;
      }
      v.push(vi); w.push(wi);
    }
    var out=[], j;
    for(i=0;i<v.length;i++) for(j=0;j<w[i];j++) out.push(v[i]);
    return out;
  }

  function pairs(n){ var P=[],i,j; for(i=0;i<n;i++) for(j=i+1;j<n;j++) P.push([i,j]); return P; }

  function configDist(Y, P){
    return P.map(function(p){
      var a=Y[p[0]], b=Y[p[1]], s=0;
      for(var q=0;q<a.length;q++){ var d=a[q]-b[q]; s+=d*d; }
      return Math.sqrt(s);
    });
  }

  /* Kruskal's stress formula 1. */
  function stress1(d, dh){
    var num=0, den=0;
    for(var i=0;i<d.length;i++){ var e=d[i]-dh[i]; num+=e*e; den+=d[i]*d[i]; }
    return den===0 ? 0 : Math.sqrt(num/den);
  }

  function fitted(d, order){
    var sorted = order.map(function(a){ return d[a]; });
    var iso = pava(sorted);
    var dh = new Array(d.length);
    for(var i=0;i<order.length;i++) dh[order[i]] = iso[i];
    return dh;
  }

  function rng(seed){
    var s = seed >>> 0 || 1;
    return function(){ s ^= s<<13; s>>>=0; s ^= s>>17; s ^= s<<5; s>>>=0; return s/4294967296; };
  }

  /* Stress-1 is scale-invariant; the gradient is not. Normalising the
     configuration each step keeps the step size meaning the same thing
     throughout the descent. */
  function normScale(Y){
    var n=Y.length, k=Y[0].length, s=0, i, j;
    for(i=0;i<n;i++) for(j=0;j<k;j++) s+=Y[i][j]*Y[i][j];
    s=Math.sqrt(s/n);
    if(!(s>0)) return Y;
    for(i=0;i<n;i++) for(j=0;j<k;j++) Y[i][j]/=s;
    return Y;
  }

  function centre(Y){
    var n=Y.length, k=Y[0].length, j, i;
    for(j=0;j<k;j++){ var m=0; for(i=0;i<n;i++) m+=Y[i][j]; m/=n;
      for(i=0;i<n;i++) Y[i][j]-=m; }
    return Y;
  }

  function nmdsOnce(D, k, Y0, iters){
    var n=D.length, P=pairs(n);
    var diss=P.map(function(p){ return D[p[0]][p[1]]; });
    var order=diss.map(function(_,i){return i;});
    order.sort(function(a,b){ return diss[a]-diss[b] || a-b; });
    var Y=Y0.map(function(r){ return r.slice(); });
    centre(Y); normScale(Y);

    function evalAt(C){
      var d=configDist(C,P), dh=fitted(d, order);
      return { d:d, dhat:dh, s:stress1(d,dh) };
    }
    /* Kruskal's gradient of stress-1 with respect to one point's coordinates. */
    function grad(st){
      var d=st.d, dh=st.dhat, S=0, num=0, i;
      for(i=0;i<d.length;i++){ S+=d[i]*d[i]; num+=(d[i]-dh[i])*(d[i]-dh[i]); }
      var G=zeros(n,k);
      if(num < 1e-30 || S < 1e-30) return G;
      for(i=0;i<P.length;i++){
        if(d[i] < 1e-12) continue;
        var c=(((d[i]-dh[i])/num) - (d[i]/S))*st.s;
        var a=P[i][0], b=P[i][1];
        for(var q=0;q<k;q++){
          var g=c*(Y[a][q]-Y[b][q])/d[i];
          G[a][q]+=g; G[b][q]-=g;
        }
      }
      return G;
    }
    /* Adaptive step. A fixed step converged linearly and was still descending
       after 6000 iterations -- which would have shipped a stress that was an
       artefact of the iteration cap rather than a property of the data. Grow
       the step while it helps, halve it when it does not. */
    var st=evalAt(Y), step=0.1, it;
    var MAXIT = iters || 500;
    for(it=0; it<MAXIT; it++){
      var G=grad(st), gn=0, i, q;
      for(i=0;i<n;i++) for(q=0;q<k;q++) gn+=G[i][q]*G[i][q];
      gn=Math.sqrt(gn);
      if(gn < 1e-13) break;
      var moved=false;
      for(var tries=0; tries<24; tries++){
        var T=zeros(n,k);
        for(i=0;i<n;i++) for(q=0;q<k;q++) T[i][q]=Y[i][q]-step*G[i][q]/gn;
        centre(T); normScale(T);
        var stT=evalAt(T);
        if(stT.s < st.s){ Y=T; st=stT; step*=1.3; moved=true; break; }
        step*=0.5;
        if(step < 1e-12) break;
      }
      if(!moved) break;
      if(st.s < 1e-12) break;
    }
    return { coords:Y, stress:st.s, iters:it, d:st.d, dhat:st.dhat, diss:diss };
  }

  /* Procrustes correlation between two configurations -- how vegan decides
     whether two random starts found the same solution. */
  function procrustes(A, B){
    var n=A.length, k=A[0].length, i, j, q;
    var X=A.map(function(r){return r.slice();}), Y=B.map(function(r){return r.slice();});
    centre(X); centre(Y);
    function norm(M){ var s=0; M.forEach(function(r){ r.forEach(function(v){ s+=v*v; }); }); return Math.sqrt(s); }
    var nx=norm(X)||1, ny=norm(Y)||1;
    X=X.map(function(r){return r.map(function(v){return v/nx;});});
    Y=Y.map(function(r){return r.map(function(v){return v/ny;});});
    var C=zeros(k,k);
    for(i=0;i<k;i++) for(j=0;j<k;j++){ var s=0; for(q=0;q<n;q++) s+=X[q][i]*Y[q][j]; C[i][j]=s; }
    /* trace of the singular values of C == max attainable correlation; for
       k<=3 get them from the eigenvalues of C'C. */
    var CtC=zeros(k,k);
    for(i=0;i<k;i++) for(j=0;j<k;j++){ var s2=0; for(q=0;q<k;q++) s2+=C[q][i]*C[q][j]; CtC[i][j]=s2; }
    var e=jacobi(CtC);
    var tr=0; e.values.forEach(function(v){ tr+=Math.sqrt(Math.max(0,v)); });
    return Math.min(1, tr);
  }

  function nmds(D, k, starts, seed){
    var n=D.length;
    var p=pcoa(D,k);
    var best=null, all=[], r=rng(seed||42), i, j, q;
    var scale=0; p.coords.forEach(function(row){ row.forEach(function(v){ scale=Math.max(scale,Math.abs(v)); }); });
    if(!(scale>0)) scale=1;
    for(i=0;i<(starts||8);i++){
      var Y0;
      if(i===0) Y0=p.coords.map(function(r2){return r2.slice();});
      else {
        Y0=[];
        for(j=0;j<n;j++){ var row=[]; for(q=0;q<k;q++) row.push((r()-0.5)*2*scale); Y0.push(row); }
      }
      var res=nmdsOnce(D,k,Y0);
      all.push(res);
      if(!best || res.stress < best.stress) best=res;
    }
    /* How many other starts landed on the same configuration? A single low
       stress from one start is not evidence the solution is stable. */
    var agree=0;
    all.forEach(function(r2){
      if(r2===best) return;
      if(r2.stress < best.stress + 1e-4 && procrustes(best.coords, r2.coords) > 0.999) agree++;
    });
    best.starts=all.length; best.agree=agree+1;
    best.stresses=all.map(function(r2){return r2.stress;}).sort(function(a,b){return a-b;});
    return best;
  }

  return { sqrtT:sqrtT, wisconsin:wisconsin, bray:bray, jaccard:jaccard, euclid:euclid,
           jacobi:jacobi, pcoa:pcoa, pava:pava, nmds:nmds, nmdsOnce:nmdsOnce,
           procrustes:procrustes, stress1:stress1, pairs:pairs, configDist:configDist };
})();
""" % VERSION
